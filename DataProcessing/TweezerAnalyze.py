"""Image analysis for one-dimensional optical tweezer arrays."""

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import gaussian_filter1d, map_coordinates
from scipy.optimize import curve_fit
from scipy.signal import find_peaks


def analyze_1D_tweezer_array(
    image,
    *,
    n_spots=15,
    magnification=25.0,
    camera_pixel_size_um=3.45,
    fit_config=None,
    plot=False,
    output_dir=None,
    output_name=None,
):
    """Analyze a nearly horizontal tweezer array, without updating hardware.

    image: TIFF path (first frame) or a numeric 2D array.
    fit_config: optional dict overriding the lower-case defaults below.
    plot: create and display diagnostic figures; otherwise create no figures.
    output_dir: optionally save tables, fit arrays, metadata, and any figures.
    output_name: export prefix; defaults to the TIFF stem or 'aod_frame'.
        Repeated calls with the same directory/prefix overwrite exports.

    Returned spots are ordered along the array, toward increasing camera x.
    fitted_intensity: 1D array of unnormalized, background-subtracted Gaussian
        peak amplitudes in camera counts from the transversely averaged strip.
        Same values as spots['amplitude_mean_counts']; not calibrated optical power.
    intensity_ratio: fitted_intensity / fitted_intensity.mean(), in the same order.
    Ratios measure background-subtracted peak intensity, not integrated power.
    No camera acquisition, RF communication, or hardware changes occur here.
    """
    defaults = dict(
        y_half_width=65, smooth_sigma=1.0, prominence_fraction=0.12,
        min_peak_distance=30, x_margin=40, core_half_width=10,
        strip_half_width=10, sigma_bounds=(0.8, 12.0),
    )
    overrides = {} if fit_config is None else dict(fit_config)
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise ValueError(f"Unknown fit_config keys: {sorted(unknown)}")
    config = {**defaults, **overrides}
    if isinstance(n_spots, (bool, np.bool_)) or not isinstance(n_spots, (int, np.integer)) or n_spots < 2:
        raise ValueError("n_spots must be an integer >= 2 to determine the array axis.")
    for key in ('y_half_width', 'min_peak_distance', 'x_margin', 'core_half_width', 'strip_half_width'):
        value = config[key]
        minimum = 0 if key in ('x_margin', 'strip_half_width') else (5 if key == 'core_half_width' else 1)
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}.")
        config[key] = int(value)
    for key in ('smooth_sigma', 'prominence_fraction'):
        value = float(config[key])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be finite and positive.")
        config[key] = value
    bounds = np.asarray(config['sigma_bounds'], dtype=float)
    if bounds.shape != (2,) or not np.isfinite(bounds).all() or not 0 < bounds[0] < bounds[1]:
        raise ValueError("sigma_bounds must contain two finite, increasing positive values.")
    config['sigma_bounds'] = bounds.tolist()
    for name, value in [('magnification', magnification), ('camera_pixel_size_um', camera_pixel_size_um)]:
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive.")
    
    N_SPOTS = int(n_spots)
    MAGNIFICATION = float(magnification)
    CAMERA_PIXEL_SIZE_UM = float(camera_pixel_size_um)
    PIXEL_SIZE_UM = CAMERA_PIXEL_SIZE_UM / MAGNIFICATION
    Y_HALF_WIDTH = config['y_half_width']
    SMOOTH_SIGMA = config['smooth_sigma']
    PROMINENCE_FRACTION = config['prominence_fraction']
    MIN_PEAK_DISTANCE = config['min_peak_distance']
    X_MARGIN = config['x_margin']
    CORE_HALF_WIDTH = config['core_half_width']
    STRIP_HALF_WIDTH = config['strip_half_width']
    SIGMA_BOUNDS = config['sigma_bounds']
    image_path = None
    
    if isinstance(image, (str, Path)):
        requested = Path(image).expanduser()
        candidates = [requested] if requested.is_absolute() else [
            root / requested for root in (Path.cwd(), *Path.cwd().parents)]
        image_path = next((p for p in candidates if p.is_file()), None)
        if image_path is None:
            raise FileNotFoundError(f"Cannot locate {requested}.")
        with Image.open(image_path) as im:
            raw = np.array(im)
    else:
        raw = np.asarray(image)
    if raw.ndim != 2 or min(raw.shape) < 3 or raw.dtype.kind not in 'uif':
        raise ValueError(f"Expected a real numeric 2D image, received {raw.shape}, {raw.dtype}.")
        
    image = raw.astype(np.float64)
    if not np.isfinite(image).all():
        raise ValueError("Image contains nonfinite values.")
    if np.ptp(image) == 0:
        raise ValueError("Image is constant; no spots can be fitted.")
        
    height, width = image.shape
    storage_saturated = bool(np.issubdtype(raw.dtype, np.integer) and np.any(raw == np.iinfo(raw.dtype).max))
    if storage_saturated:
        warnings.warn("Pixels reach the storage maximum. Camera saturation may also occur below this limit.")
        
    figures = {}
    # search the y ROI band
    brightest_row = int(np.argmax(gaussian_filter1d(image.sum(axis=1), 2)))
    y_min, y_max = max(0, brightest_row - Y_HALF_WIDTH), min(height, brightest_row + Y_HALF_WIDTH + 1)
    x_min, x_max = 0, width

    # search the x ROI band
    x_detection = np.arange(x_min, x_max)
    profile_detection = image[y_min:y_max, x_min:x_max].sum(axis=0)
    smoothed = gaussian_filter1d(profile_detection, SMOOTH_SIGMA)

    prominence = PROMINENCE_FRACTION * (smoothed.max() - np.median(smoothed))
    peaks, properties = find_peaks(smoothed, distance=MIN_PEAK_DISTANCE, prominence=max(prominence, 1e-9))
    if len(peaks) < N_SPOTS:
        raise RuntimeError(f"Found {len(peaks)} peaks, expected {N_SPOTS}. Adjust the detection settings or Y_HALF_WIDTH.")
    if len(peaks) > N_SPOTS:
        warnings.warn(f"Found {len(peaks)} candidates; keeping the {N_SPOTS} most prominent. Inspect the overlay.")
        peaks = peaks[np.argsort(properties["prominences"])[-N_SPOTS:]]
    centers_initial = np.sort(x_detection[peaks]).astype(float)

    if np.any((centers_initial < x_min) | (centers_initial >= x_max)):
        raise ValueError("Centers must lie in the ROI.")
    x_min = max(x_min, int(np.floor(centers_initial[0])) - X_MARGIN)
    x_max = min(x_max, int(np.ceil(centers_initial[-1])) + X_MARGIN + 1)
    x = np.arange(x_min, x_max, dtype=float)
    roi = image[y_min:y_max, x_min:x_max]
    
    if plot:
        fig, axis = plt.subplots(figsize=(14, 6), constrained_layout=True)
        axis.imshow(roi, origin="upper", cmap="inferno", aspect="equal",
                       extent=(x_min - .5, x_max - .5, y_max - .5, y_min - .5))
        for i, center in enumerate(centers_initial, 1):
            axis.axvline(center, color="cyan", alpha=.35, linewidth=.7)
            axis.text(center, y_min + 8, str(i), color="cyan", ha="center")
        axis.set(xlabel="x (pixel)", ylabel="y (pixel)", title="Detected tweezers")
        plt.show()
        figures["detection"] = fig

    def core_gaussian(coords, background, amplitude, xc, yc, sx, sy):
        xx, yy = coords
        return (background + amplitude * np.exp(-0.5 * (((xx-xc)/sx)**2 + ((yy-yc)/sy)**2))).ravel()

    core_parameters = []
    core_patches = []            # measured patches, fitted images, and image-coordinate bounds
    core_rmse = []
    core_bound_flags = []
    for id_spot, x_initial in enumerate(centers_initial, 1):
        x_guess = int(round(x_initial))
        search = image[y_min:y_max, max(0, x_guess-3):min(width, x_guess+4)]
        y_guess = y_min + int(np.argmax(gaussian_filter1d(search.sum(axis=1), 1)))
        xa, xb = max(0, x_guess-CORE_HALF_WIDTH), min(width, x_guess+CORE_HALF_WIDTH+1)  # the x limit of the patch
        ya, yb = max(0, y_guess-CORE_HALF_WIDTH), min(height, y_guess+CORE_HALF_WIDTH+1) # the y limit of the patch
        patch = image[ya:yb, xa:xb]
        yy, xx = np.mgrid[ya:yb, xa:xb]
        bg = np.percentile(patch, 10)
        guess = [bg, max(patch.max()-bg, 1), x_initial, y_guess, 4., 4.]
        lo = [-np.inf, 0, xa, ya, .1, .1]
        hi = [np.inf, np.inf, xb-1, yb-1, CORE_HALF_WIDTH, CORE_HALF_WIDTH]
        try:
            fitted_parameters, _ = curve_fit(core_gaussian, (xx, yy), patch.ravel(), p0=guess,
                               bounds=(lo, hi), x_scale="jac", max_nfev=3000)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(f"Cannot locate spot {id_spot}; inspect detection and CORE_HALF_WIDTH.") from exc
        core_at_bound = bool(np.any(np.isclose(fitted_parameters, lo, atol=.02, rtol=0) | np.isclose(fitted_parameters, hi, atol=.02, rtol=0)))
        if core_at_bound:
            warnings.warn(f"Spot {id_spot}: local fit is near a bound; inspect the center overlay.")
        core_model = core_gaussian((xx, yy), *fitted_parameters).reshape(patch.shape)
        core_patches.append((patch.copy(), core_model, (xa, xb, ya, yb)))
        core_rmse.append(np.sqrt(np.mean((patch-core_model)**2)))
        core_bound_flags.append(core_at_bound)
        core_parameters.append(fitted_parameters)
    core_parameters = np.asarray(core_parameters)

    # the centers of the gaussian cores
    centers_xy = core_parameters[:, 2:4]

    array_origin = centers_xy.mean(axis=0)
    _, _, vh = np.linalg.svd(centers_xy-array_origin, full_matrices=False)
    xp_direction = vh[0]
    if xp_direction[0] < 0:
        xp_direction = -xp_direction
    yp_direction = np.array([-xp_direction[1], xp_direction[0]])
    angle_deg = float(np.degrees(np.arctan2(xp_direction[1], xp_direction[0])))
    projected_centers = (centers_xy-array_origin) @ xp_direction # project the points on the titled axis

    spot_order = np.argsort(projected_centers)
    initial_xp = projected_centers[spot_order]
    transverse_offsets = (centers_xy-array_origin) @ yp_direction



    # Use the same left-to-right order as the tilted-axis results.
    ordered_core = core_parameters[spot_order]
    core_fwhm_factor = 2*np.sqrt(2*np.log(2))
    core_results = pd.DataFrame({
        "spot": np.arange(1, N_SPOTS+1),
        "core_background_counts": ordered_core[:, 0],
        "core_amplitude_counts": ordered_core[:, 1],
        "core_x_center_px": ordered_core[:, 2],
        "core_y_center_px": ordered_core[:, 3],
        "core_sigma_x_px": ordered_core[:, 4],
        "core_sigma_y_px": ordered_core[:, 5],
        "core_sigma_x_um": ordered_core[:, 4]*PIXEL_SIZE_UM,
        "core_sigma_y_um": ordered_core[:, 5]*PIXEL_SIZE_UM,
        "core_fwhm_x_um": core_fwhm_factor*ordered_core[:, 4]*PIXEL_SIZE_UM,
        "core_fwhm_y_um": core_fwhm_factor*ordered_core[:, 5]*PIXEL_SIZE_UM,
        "core_rmse_counts": np.asarray(core_rmse)[spot_order],
        "core_near_fit_bound": np.asarray(core_bound_flags)[spot_order],
    })

    if plot:
        core_vmin = min(min(data.min(), model.min()) for data, model, _ in core_patches)
        core_vmax = max(max(data.max(), model.max()) for data, model, _ in core_patches)
        core_residual_limit = max(max(np.max(np.abs(data-model)) for data, model, _ in core_patches), 1e-12)
        fig_cores = []
        spots_per_figure = N_SPOTS  # keep every spot together in one figure
        for start in range(0, N_SPOTS, spots_per_figure):
            stop = min(start+spots_per_figure, N_SPOTS)
            fig_core, axes = plt.subplots(3, stop-start, figsize=(max(12, 2*N_SPOTS), 7),
                                          squeeze=False, constrained_layout=True)
            for column, ordered_index in enumerate(range(start, stop)):
                original_index = spot_order[ordered_index]
                data, model, (xa, xb, ya, yb) = core_patches[original_index]
                extent = (xa-.5, xb-.5, yb-.5, ya-.5)
                for row, panel in enumerate([data, model, data-model]):
                    ax = axes[row, column]
                    if row < 2:
                        intensity_artist = ax.imshow(panel, origin="upper", extent=extent,
                                                     cmap="inferno", vmin=core_vmin, vmax=core_vmax)
                        ax.plot(ordered_core[ordered_index, 2], ordered_core[ordered_index, 3], "c+", ms=7, mew=1)
                    else:
                        residual_artist = ax.imshow(panel, origin="upper", extent=extent, cmap="RdBu_r",
                                                    vmin=-core_residual_limit, vmax=core_residual_limit)
                        ax.set_xlabel("Image x (px)")
                    ax.tick_params(labelsize=7)
                axes[0, column].set_title(f"Spot {ordered_index+1}")
            for row, label in enumerate(["Data", "2D Gaussian fit", "Data − fit"]):
                axes[row, 0].set_ylabel(label + " / image y (px)")
            fig_core.colorbar(intensity_artist, ax=axes[:2, :].ravel().tolist(), shrink=.85, label="Camera counts")
            fig_core.colorbar(residual_artist, ax=axes[2, :].ravel().tolist(), shrink=.85, label="Residual counts")
            fig_core.suptitle(f"Local 2D fits — spots {start+1}–{stop}")
            fig_cores.append(fig_core)
            plt.show()
        figures["cores"] = fig_cores

    if not isinstance(STRIP_HALF_WIDTH, (int, np.integer)) or STRIP_HALF_WIDTH < 0:
        raise ValueError("STRIP_HALF_WIDTH must be a nonnegative integer.")
    
    xp = np.arange(np.floor(initial_xp[0])-X_MARGIN, np.ceil(initial_xp[-1])+X_MARGIN+1)
    yp = np.arange(-STRIP_HALF_WIDTH, STRIP_HALF_WIDTH+1)
    xxp, yyp = np.meshgrid(xp, yp)

    # Convert the rotated window coordinate back to the original axes and extract the data
    sample_x = array_origin[0] + xxp*xp_direction[0] + yyp*yp_direction[0]
    sample_y = array_origin[1] + xxp*xp_direction[1] + yyp*yp_direction[1]
    if np.any((sample_x < 0) | (sample_x > width-1) | (sample_y < 0) | (sample_y > height-1)):
        raise ValueError("The strip leaves the image; reduce X_MARGIN or STRIP_HALF_WIDTH.")
    strip = map_coordinates(image, [sample_y, sample_x], order=1, mode="constant", cval=np.nan)
    along_profile = strip.mean(axis=0)


    if plot:
        fig_axis, ax = plt.subplots(figsize=(14, 4), constrained_layout=True)
        ax.imshow(roi, origin="upper", cmap="inferno",
                  extent=(x_min-.5, x_max-.5, y_max-.5, y_min-.5))
        ax.scatter(centers_xy[:, 0], centers_xy[:, 1], s=30, facecolors="none", edgecolors="cyan", label="2D centers")
        ax.plot(array_origin[0]+xp*xp_direction[0], array_origin[1]+xp*xp_direction[1], color="cyan", lw=1, label="Array axis")
        for edge in [-STRIP_HALF_WIDTH, STRIP_HALF_WIDTH]:
            ax.plot(array_origin[0]+xp*xp_direction[0]+edge*yp_direction[0],
                    array_origin[1]+xp*xp_direction[1]+edge*yp_direction[1], "c--", lw=.8)
        ax.set(xlabel="Image x (pixels)", ylabel="Image y (pixels)", title=f"Sampling strip along the {angle_deg:.2f}° tilted array")
        ax.legend(fontsize=8)
        plt.show()
        figures["sampling_strip"] = fig_axis

    xp_ref = xp.mean()
    FWHM_FACTOR = 2*np.sqrt(2*np.log(2))

    def gaussian_components(xp_values, triples):
        amplitude, center, sigma = np.asarray(triples).reshape(-1, 3).T
        return amplitude[:, None]*np.exp(-.5*((np.asarray(xp_values)[None, :]-center[:, None])/sigma[:, None])**2)

    def tilted_model(xp_values, b0, b1, *triples):
        return b0 + b1*(xp_values-xp_ref) + gaussian_components(xp_values, triples).sum(axis=0)

    background_guess = np.percentile(along_profile, 20)
    amplitude_guess = np.maximum(np.interp(initial_xp, xp, along_profile)-background_guess, 1.)
    sx, sy = core_parameters[spot_order, 4], core_parameters[spot_order, 5]
    sigma_guess = 1/np.sqrt((xp_direction[0]/sx)**2 + (xp_direction[1]/sy)**2)
    sigma_guess = np.clip(sigma_guess, SIGMA_BOUNDS[0] + 0.01*np.diff(SIGMA_BOUNDS)[0], SIGMA_BOUNDS[1] - 0.01*np.diff(SIGMA_BOUNDS)[0])
    p0 = np.r_[background_guess, 0., np.column_stack([amplitude_guess, initial_xp, sigma_guess]).ravel()]
    lower = np.r_[-np.inf, -np.inf, np.column_stack([np.zeros(N_SPOTS), initial_xp-CORE_HALF_WIDTH, np.full(N_SPOTS, SIGMA_BOUNDS[0])]).ravel()]
    upper = np.r_[np.inf, np.inf, np.column_stack([np.full(N_SPOTS, np.inf), initial_xp+CORE_HALF_WIDTH, np.full(N_SPOTS, SIGMA_BOUNDS[1])]).ravel()]
    popt, pcov = curve_fit(tilted_model, xp, along_profile, p0=p0, bounds=(lower, upper),
                           x_scale="jac", max_nfev=5000)

    parameters = popt[2:].reshape(N_SPOTS, 3)
    fitted_centers = parameters[:, 1]
    prediction = tilted_model(xp, *popt)
    residual = along_profile-prediction
    background = popt[0]+popt[1]*(xp-xp_ref)
    r_squared = 1-np.sum(residual**2)/np.sum((along_profile-along_profile.mean())**2)
    rmse = np.sqrt(np.mean(residual**2))
    distance_um = (xp-fitted_centers[0])*PIXEL_SIZE_UM
    center_distances_um = (fitted_centers-fitted_centers[0])*PIXEL_SIZE_UM
    separations_um = np.diff(fitted_centers)*PIXEL_SIZE_UM
    near_bound = (np.isclose(popt, lower, atol=.02, rtol=0) | np.isclose(popt, upper, atol=.02, rtol=0))[2:].reshape(-1, 3).any(axis=1)
    if near_bound.any():
        warnings.warn("Some Gaussian parameters are near bounds. Inspect the fit before using the results.")
    if not np.isfinite(pcov).all():
        warnings.warn("Covariance is not finite; parameter uncertainties are unreliable.")


    results = pd.DataFrame({
        "spot": np.arange(1, N_SPOTS+1), "distance_from_first_um": center_distances_um,
        "xp_center_px": fitted_centers, "amplitude_mean_counts": parameters[:, 0],
        "sigma_along_px": parameters[:, 2], "sigma_along_um": parameters[:, 2]*PIXEL_SIZE_UM,
        "fwhm_along_um": FWHM_FACTOR*parameters[:, 2]*PIXEL_SIZE_UM,
        "radius_1e2_along_um": 2*parameters[:, 2]*PIXEL_SIZE_UM,
        "separation_to_next_um": np.r_[separations_um, np.nan], "near_fit_bound": near_bound
    })

    # Normalize amplitudes before plotting; the same ratios are saved below.
    for table, amplitude_column, ratio_column in [
        (results, "amplitude_mean_counts", "amplitude_ratio_to_mean"),
        (core_results, "core_amplitude_counts", "core_amplitude_ratio_to_mean"),
    ]:
        amplitudes = table[amplitude_column].to_numpy(dtype=float)
        mean_amplitude = amplitudes.mean()
        if not np.isfinite(amplitudes).all() or not np.isfinite(mean_amplitude) or mean_amplitude <= 0:
            raise ValueError(f"Cannot normalize {amplitude_column}: amplitudes must be finite with a positive mean.")
        table[ratio_column] = amplitudes / mean_amplitude


    if plot:
        fig_fit, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1.3, 1.3]}, constrained_layout=True)
        axes[0].plot(distance_um, along_profile, color="black", lw=1, label="Tilted-strip data")
        axes[0].plot(distance_um, prediction, color="tab:red", lw=1.5, label=f"{N_SPOTS}-Gaussian fit")
        for i, component in enumerate(gaussian_components(xp, popt[2:])):
            axes[0].plot(distance_um, background+component, lw=.7, alpha=.6,
                         label="Individual Gaussians + background" if i == 0 else None)
        for center_um in center_distances_um:
            axes[0].axvline(center_um, color="gray", lw=.5, alpha=.35)
        top = axes[0].secondary_xaxis("top")
        top.set_xticks(center_distances_um)
        top.set_xticklabels([f"{v:.1f}" for v in center_distances_um], rotation=45, ha="left", fontsize=8)
        top.set_xlabel("Fitted spot positions relative to first spot (µm)")
        axes[0].set(ylabel="Mean camera counts", title=f"Tilted-axis fit: {angle_deg:.2f}°, {PIXEL_SIZE_UM:g} µm/pixel (M={MAGNIFICATION:g})")
        # axes[0].legend(fontsize=8)
        # axes[1].plot(distance_um, residual, lw=.8)
        # axes[1].axhline(0, color="black", lw=.7)
        # axes[1].set_ylabel("Data − fit")
        midpoints_um = (center_distances_um[:-1]+center_distances_um[1:])/2
        axes[1].plot(midpoints_um, separations_um, "o-", ms=4)
        axes[1].axhline(separations_um.mean(), color="gray", ls="--", label=f"Mean {separations_um.mean():.2f} µm")
        for midpoint, separation in zip(midpoints_um, separations_um):
            axes[1].annotate(f"{separation:.2f}", (midpoint, separation), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=7)
        axes[1].margins(y=.4)
        axes[1].set_ylabel("Adjacent separation (µm)")
        axes[1].legend(fontsize=8)

        # Third panel: peak amplitudes relative to each fit type's own mean.
        axes[2].plot(center_distances_um, results["amplitude_ratio_to_mean"], "o-", ms=4, label="Tilted 1D amplitude / mean")
        axes[2].plot(center_distances_um, core_results["core_amplitude_ratio_to_mean"], "s--", ms=4, label="Local 2D amplitude / mean")
        axes[2].axhline(1.0, color="gray", ls=":", label="Average = 1")
        axes[2].set(xlabel="Distance along tilted array from first fitted spot (µm)", ylabel="Amplitude / mean")
        axes[2].margins(y=.2)
        axes[2].legend(fontsize=8)
        plt.show()
        figures["fit"] = fig_fit

    combined_results = results.merge(core_results, on="spot", how="left", validate="one_to_one")
    ratios = results['amplitude_ratio_to_mean'].to_numpy(dtype=float)
    if not np.isfinite(ratios).all() or np.any(ratios <= 0):
        raise ValueError("All fitted intensities must be finite and strictly positive for feedback.")
    correction = 1.0 / ratios
    if not np.isfinite(correction).all():
        raise ValueError("Intensity correction overflowed; inspect weak or missing spots.")
    combined_results['intensity_correction_ratio'] = correction
    issues = []
    if storage_saturated:
        issues.append('pixels reach storage maximum')
    if np.any(core_bound_flags) or near_bound.any():
        issues.append('fit parameters near bounds')
    if not np.isfinite(pcov).all():
        issues.append('nonfinite fit covariance')
    if np.any(np.diff(fitted_centers) <= 0):
        issues.append('fitted spot ordering is not strictly increasing')
    metadata = {
        'image': str(image_path.resolve()) if image_path else None,
        'frame': 0, 'n_spots': N_SPOTS, 'fit_config': config,
        'camera_pixel_size_um': CAMERA_PIXEL_SIZE_UM,
        'magnification': MAGNIFICATION, 'effective_pixel_size_um': PIXEL_SIZE_UM,
        'array_angle_deg': angle_deg, 'array_origin_xy_px': array_origin.tolist(),
        'direction_xy': xp_direction.tolist(), 'xp_reference_px': float(xp_ref),
        'r_squared': float(r_squared), 'rmse_counts': float(rmse),
        'mean_separation_um': float(separations_um.mean()),
        'relative_intensity_std': float(np.std(ratios)),
        'quality_issues': issues,
        'spot_order': 'along array toward increasing camera x; verify RF-tone mapping',
        'amplitude_ratio_definition': 'background-subtracted fitted peak amplitude / arithmetic mean; not integrated power',
        'parameter_order': 'b0, b1, then (amplitude, xp_center_px, sigma_px) per spot',
        'local_core_parameter_order': 'background, amplitude, x_center, y_center, sigma_x, sigma_y',
        'weighting': 'unweighted least squares',
        'profile': 'bilinear interpolation, transverse mean',
    }
    profile = pd.DataFrame({
        'xp_px': xp, 'distance_um': distance_um, 'measured_counts': along_profile,
        'fitted_counts': prediction, 'background_counts': background,
        'residual_counts': residual,
    })
    if output_dir is not None:
        directory = Path(output_dir).expanduser()
        name = output_name if output_name is not None else (image_path.stem if image_path else 'aod_frame')
        if not isinstance(name, str) or not name or Path(name).name != name or name in ('.', '..'):
            raise ValueError('output_name must be a nonempty filename prefix, without directories.')
        directory.mkdir(parents=True, exist_ok=True)
        stem = name + '_tilted_only'
        for suffix, table in [('gaussians', results), ('2d_gaussians', core_results),
                              ('combined_results', combined_results), ('profile', profile)]:
            table.to_csv(directory / f'{stem}_{suffix}.csv', index=False)
        np.savez(directory / f'{stem}_fit.npz', parameters=popt, covariance=pcov,
                 origin_xy=array_origin, direction_xy=xp_direction, xp_px=xp,
                 xp_reference=xp_ref, local_core_parameters=core_parameters,
                 initial_centers_xp=initial_xp)
        for key, value in figures.items():
            for page, figure in enumerate(value if isinstance(value, list) else [value], 1):
                figure.savefig(directory / f'{stem}_{key}_{page:02d}.png', dpi=150, bbox_inches='tight')
        (directory / f'{stem}_metadata.json').write_text(json.dumps(metadata, indent=2))
    return {
        'spots': combined_results, 'intensity_ratio': ratios.copy(),
        'fitted_intensity': results['amplitude_mean_counts'].to_numpy(dtype=float, copy=True),
        'correction_ratio': correction, 'angle_deg': angle_deg,
        'r_squared': float(r_squared), 'rmse_counts': float(rmse),
        'quality_issues': issues, 'profile': profile, 'metadata': metadata,
        'parameters': popt, 'covariance': pcov, 'figures': figures,
    }
