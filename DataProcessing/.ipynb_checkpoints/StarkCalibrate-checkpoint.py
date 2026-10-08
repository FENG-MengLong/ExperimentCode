## StarkCalibrate
## Author: Carlos Owens
## Last updated: 12 August 2026

# import packages; (*) = necessary for this 
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator # (*)
from DataProcessing import Readout

from matplotlib import rcParams
rcParams['font.family'] = 'sans-serif'
rcParams['mathtext.fontset'] = 'stix'
rcParams['axes.unicode_minus'] = False
rcParams.update({
	'font.size': 14,
	'axes.titlesize': 14,
	'axes.labelsize': 14,
	'xtick.labelsize': 14,
	'ytick.labelsize': 14,
	'legend.fontsize': 14,
	'figure.titlesize': 14,
	'legend.frameon': False,
})

# define the symmetry error between the two sides of a proposed Stark-map center
def symmetry_error(x, y, Z, x_center, half_width=0.6, n_points=121):
    """
    Calculate left/right mismatch about x = x_center using a FIXED
    comparison window. Every accepted candidate is therefore scored from
    the same voltage span, avoiding spuriously good minima near scan edges.

    Parameters
    ----------
    x, y : array-like
        Electrode voltage and 480-nm laser-frequency coordinates.
    Z : array-like
        Average photon counts, shape (len(y), len(x)).
    x_center : float
        Candidate compensation voltage.
    half_width : float
        Voltage extent compared on each side of x_center.
    n_points : int
        Number of offsets sampled from the center to half_width.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    Z = np.asarray(Z)

    # Require the complete, identical comparison window for every candidate.
    if (x_center - half_width < x.min()) or (x_center + half_width > x.max()):
        return np.inf

    interpolator = RegularGridInterpolator(
        (y, x), Z, bounds_error=False, fill_value=np.nan
    )

    # Do not duplicate the center point: it has zero left/right mismatch.
    dx = np.linspace(0.0, half_width, n_points)[1:]
    Y, DX = np.meshgrid(y, dx, indexing="ij")

    left_points = np.column_stack([Y.ravel(), (x_center - DX).ravel()])
    right_points = np.column_stack([Y.ravel(), (x_center + DX).ravel()])

    Z_left = interpolator(left_points).reshape(Y.shape)
    Z_right = interpolator(right_points).reshape(Y.shape)
    good = np.isfinite(Z_left) & np.isfinite(Z_right)

    if not np.any(good):
        return np.inf

    numerator = np.mean((Z_left[good] - Z_right[good])**2)

    # Symmetric normalization: neither side is privileged.
    denominator = np.mean(0.5 * (Z_left[good]**2 + Z_right[good]**2))
    if denominator <= 0 or not np.isfinite(denominator):
        return np.inf

    return numerator / denominator


# used to readout Stark map data from folder
def Stark_map_readout(date: str, plot_id: int):
    root_dir = 'X:/migratedData/Rydberg_QIS/data'
    # root_dir = f"/run/user/1000/gvfs/smb-share:server=lsa-graithel-win.turbo.storage.umich.edu,share=lsa-graithel/migratedData/Rydberg_QIS/data"   # Linux
    X, Y, Z, notes = Readout.read_saved_csv_by_id(root_dir = root_dir, date = date, plot_id = plot_id)
    Z = Z.T # flip this array so the dimensions match X and Y

    return X, Y, Z, notes

# choose an automatic range of comparison half-widths from the measured scan
# and look for a compensation voltage that is stable across those widths.
def _auto_widths(x, min_half_width=None, max_half_width=None, n_widths=16):
    x = np.asarray(x, dtype=float)
    span = float(x.max() - x.min())
    if span <= 0:
        raise ValueError("Voltage axis must span a nonzero range.")

    # Keep enough room for a meaningful comparison, but do not let the widest
    # window collapse the allowed center range to a single point.
    if min_half_width is None:
        min_half_width = 0.08 * span
    if max_half_width is None:
        max_half_width = 0.35 * span

    min_half_width = max(float(min_half_width), span / max(len(x) - 1, 1))
    max_half_width = min(float(max_half_width), 0.49 * span)
    if min_half_width >= max_half_width:
        raise ValueError("Automatic half-width bounds leave no usable range.")

    return np.linspace(min_half_width, max_half_width, int(n_widths))


def _center_for_width(x, y, Z, half_width, n_candidates=500,
                      n_compare_points=121):
    search_min = x.min() + half_width
    search_max = x.max() - half_width
    if search_min >= search_max:
        return np.nan, np.inf, np.array([]), np.array([])

    candidates = np.linspace(search_min, search_max, n_candidates)
    errors = np.array([
        symmetry_error(x, y, Z, xc, half_width=half_width,
                       n_points=n_compare_points)
        for xc in candidates
    ])
    finite = np.isfinite(errors)
    if not np.any(finite):
        return np.nan, np.inf, candidates, errors
    idx = np.nanargmin(errors)
    return candidates[idx], errors[idx], candidates, errors


def _select_stable_width(widths, centers, errors):
    """Select a width from the flattest local region of V0(width).

    The score uses the local slope of the fitted center versus half-width and a
    small preference for larger windows.  The returned compensation voltage is
    the median of the selected width and its immediate neighbors, making the
    result less sensitive to the discrete width grid.
    """
    widths = np.asarray(widths)
    centers = np.asarray(centers)
    errors = np.asarray(errors)
    good = np.isfinite(centers) & np.isfinite(errors)
    if np.sum(good) < 3:
        raise ValueError("Too few valid half-widths for automatic selection.")

    w = widths[good]
    c = centers[good]
    e = errors[good]
    slope = np.abs(np.gradient(c, w))

    # Robustly scale the two terms.  Error is only a weak tie-breaker: the
    # primary criterion is stability of the inferred center as width changes.
    slope_scale = np.nanmedian(slope) + 1e-12
    err_scale = np.nanmedian(e) + 1e-12
    width_bonus = (w - w.min()) / max(w.max() - w.min(), 1e-12)
    score = slope / slope_scale + 0.15 * e / err_scale - 0.10 * width_bonus

    # Avoid selecting an endpoint unless there are only three valid widths.
    choices = np.arange(len(w))
    if len(w) > 3:
        choices = choices[1:-1]
    j = choices[np.argmin(score[choices])]

    lo = max(0, j - 1)
    hi = min(len(w), j + 2)
    best_center = float(np.median(c[lo:hi]))
    best_width = float(w[j])
    center_spread = float(np.ptp(c[lo:hi])) if hi - lo > 1 else 0.0
    return best_width, best_center, center_spread, w, c, e, score


# used to search for symmetry point in Stark map, with diagnostics
def symmetry_search(date: str, plot_id: int, axis: int, plot_best=False,
                    plot_all=False, half_width="auto", n_candidates=500,
                    n_compare_points=121, n_widths=16,
                    min_half_width=None, max_half_width=None):
    """Find the Stark-map symmetry center.

    half_width may be a number (fixed-window search) or "auto".  Auto mode
    repeats the fit over a range of fixed half-widths and selects a locally
    stable region of compensation voltage versus half-width.  Importantly,
    each individual fit still uses one fixed width for every candidate center,
    so the original edge/overlap bias is not reintroduced.
    """
    X_data, Y_data, Z_data, notes = Stark_map_readout(date, plot_id)
    X_data = np.asarray(X_data, dtype=float)
    Y_data = np.asarray(Y_data, dtype=float)
    Z_data = np.asarray(Z_data, dtype=float)

    auto = isinstance(half_width, str) and half_width.lower() == "auto"

    if auto:
        widths = _auto_widths(X_data, min_half_width=min_half_width,
                              max_half_width=max_half_width,
                              n_widths=n_widths)
        centers, min_errors = [], []
        for width in widths:
            center, err, _, _ = _center_for_width(
                X_data, Y_data, Z_data, width,
                n_candidates=n_candidates,
                n_compare_points=n_compare_points
            )
            centers.append(center)
            min_errors.append(err)

        (chosen_width, best_center, center_spread, valid_widths,
         valid_centers, valid_errors, stability_score) = _select_stable_width(
            widths, centers, min_errors
        )
        half_width = chosen_width
    else:
        half_width = float(half_width)
        best_center, _, _, _ = _center_for_width(
            X_data, Y_data, Z_data, half_width,
            n_candidates=n_candidates,
            n_compare_points=n_compare_points
        )
        if not np.isfinite(best_center):
            raise ValueError("No valid candidate centers for this half-width.")
        center_spread = np.nan

    # Recompute the selected fixed-width error curve for diagnostics.
    fitted_center, _, candidate_centers, errors = _center_for_width(
        X_data, Y_data, Z_data, half_width,
        n_candidates=n_candidates,
        n_compare_points=n_compare_points
    )
    # In auto mode use the local median center for robustness; in fixed mode the
    # minimum and returned center are identical.
    if not auto:
        best_center = fitted_center

    search_min = X_data.min() + half_width
    search_max = X_data.max() - half_width

    if plot_best:
        interpolator = RegularGridInterpolator(
            (Y_data, X_data), Z_data, bounds_error=False, fill_value=np.nan
        )
        x_plot = np.linspace(best_center - half_width,
                             best_center + half_width,
                             max(2 * n_compare_points - 1, 101))
        X, Y = np.meshgrid(x_plot, Y_data)
        pts = np.column_stack([Y.ravel(), X.ravel()])
        Z_window = interpolator(pts).reshape(Y.shape)
        X_source = 2 * best_center - X
        mirror_pts = np.column_stack([Y.ravel(), X_source.ravel()])
        Z_mirror = interpolator(mirror_pts).reshape(Y.shape)

        fig, ax = plt.subplots(figsize=(9, 6))
        pcm1 = ax.pcolormesh(X, Y, Z_window, shading="auto", alpha=0.5)
        ax.pcolormesh(X, Y, Z_mirror, shading="auto", alpha=0.5)
        ax.axvline(best_center, linestyle="--", linewidth=2,
                   label=f"Compensation voltage for axis {axis} = {best_center:.3f} V")
        ax.axvline(best_center - half_width, linestyle=":", linewidth=1)
        ax.axvline(best_center + half_width, linestyle=":", linewidth=1)
        ax.set_xlabel(notes["xlabel"])
        ax.set_ylabel(notes["ylabel"])
        cbar = fig.colorbar(pcm1, ax=ax)
        cbar.set_label(notes["zlabel"])
        ax.legend()
        plt.show()

    if plot_all:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(candidate_centers, errors, label="Selected fixed-window error")
        ax.axvline(best_center, linestyle="--",
                   label=f"Reported center = {best_center:.3f} V")
        ax.axvspan(X_data.min(), search_min, alpha=0.12,
                   label="Rejected: incomplete window")
        ax.axvspan(search_max, X_data.max(), alpha=0.12)
        ax.set_xlabel("Candidate symmetry center (V)")
        ax.set_ylabel("Normalized symmetry error")
        ax.legend()
        plt.show()

        if auto:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(valid_widths, valid_centers, marker="o")
            ax.axvline(half_width, linestyle="--",
                       label=f"Selected half-width = {half_width:.3f} V")
            ax.axhline(best_center, linestyle=":",
                       label=f"Reported center = {best_center:.3f} V")
            ax.set_xlabel("Comparison half-width (V)")
            ax.set_ylabel("Best-fit compensation voltage (V)")
            ax.legend()
            plt.show()

    print(f"Estimated compensation voltage for axis {axis}: {best_center:.3f} V")
    if auto:
        print(f"Automatically selected comparison half-width: {half_width:.3f} V")
        print(f"Local center spread across neighboring widths: {center_spread:.3f} V")
    else:
        print(f"Fixed comparison half-width: {half_width:.3f} V")
    return best_center
