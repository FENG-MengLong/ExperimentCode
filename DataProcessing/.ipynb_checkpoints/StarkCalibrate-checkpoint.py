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

# define the symmetry error between the original and reflected Stark maps
def symmetry_error(x, y, Z, x_center):
    """
    Calculate the mismatch between Z(x,y) and its reflection
    about x = x_center.

    Assumes x and y define a regular grid and Z has shape
    (len(y), len(x)).

    Parameters:
    x: array-like
        electrode voltage values (V).
    y: array-like
        480-nm laser frequency (kHz).
    Z: array_like
        average number of photon counts (unitless).
    x_center: float
        estimated line center of Stark map (V).
        
    Returns:
    error: float
        estimated symmetry error for proposed line center x_center.
    """

    # reflected x coordinate
    x_mirror = 2 * x_center - x

    # only use the portion that overlaps the original domain
    valid = ((x_mirror >= x.min()) & (x_mirror <= x.max()))

    if np.sum(valid) < 2:
        return np.inf

    # interpolator for Z(y, x)
    interpolator = RegularGridInterpolator((y, x), Z, bounds_error = False, fill_value = np.nan)

    # coordinates at which we want the reflected data
    X, Y = np.meshgrid(x[valid], y)

    # to find the mirrored value at x, evaluate the original data at 2*xc - x
    X_source = 2 * x_center - X

    points = np.column_stack([Y.ravel(), X_source.ravel()])

    Z_mirror = interpolator(points).reshape(Y.shape)

    # original data at same locations
    Z_original = Z[:, valid]

    # ignore locations outside interpolation range
    good = np.isfinite(Z_mirror) & np.isfinite(Z_original)

    if not np.any(good):
        return np.inf

    # normalized RMS error
    numerator = np.mean((Z_original[good] - Z_mirror[good])**2)
    denominator = np.mean(Z_original[good]**2)
    error = numerator / denominator

    return error

# used to readout Stark map data from folder
def Stark_map_readout(date: str, plot_id: int):
    root_dir = 'X:/migratedData/Rydberg_QIS/data'
    # root_dir = f"/run/user/1000/gvfs/smb-share:server=lsa-graithel-win.turbo.storage.umich.edu,share=lsa-graithel/migratedData/Rydberg_QIS/data"   # Linux
    X, Y, Z, notes = Readout.read_saved_csv_by_id(root_dir = root_dir, date = date, plot_id = plot_id)
    Z = Z.T # flip this array so the dimensions match X and Y

    return X, Y, Z, notes

# used to search for symmetry point in Stark map, optional plotting of error curve
def symmetry_search(date:str, plot_id: int, axis: int, plot_best = False, plot_all = False):
    X_data, Y_data, Z_data, notes = Stark_map_readout(date, plot_id)
    candidate_centers = np.linspace(X_data.min(), X_data.max(), 500)
    errors = np.array([symmetry_error(X_data, Y_data, Z_data, xc) for xc in candidate_centers])
    
    best_index = np.nanargmin(errors)
    best_center = candidate_centers[best_index]

    if plot_best:
        X, Y = np.meshgrid(X_data, Y_data)
        X_mirror = 2 * best_center - X
        
        fig, ax = plt.subplots(figsize = (9, 6))
    
        # original Stark map
        pcm1 = ax.pcolormesh(X, Y, Z_data, shading = "auto", alpha = 0.5)
        
        # mirrored Stark map
        pcm2 = ax.pcolormesh(X_mirror, Y, Z_data, shading = "auto", alpha = 0.5)
        
        # plot the symmetry axis as well
        ax.axvline(best_center, linestyle = "--", linewidth = 2, label = f"Compensation voltage for axis {axis} = {best_center:.3f} V")
        
        ax.set_xlabel(notes["xlabel"])
        ax.set_ylabel(notes["ylabel"])
        
        # add colorbar to the figure
        cbar = fig.colorbar(pcm1, ax = ax)
        cbar.set_label(notes["zlabel"])
        
        ax.legend()
        plt.show()

        #return fig
        
    if plot_all:
        fig, ax = plt.subplots(figsize = (8, 4))
        ax.plot(candidate_centers, errors)
        ax.axvline(best_center, linestyle = "--", label = f"Compensation voltage for axis {axis} = {best_center:.3f} V")
        
        ax.set_xlabel("Candidate symmetry center (V)")
        ax.set_ylabel("Normalized symmetry error")
        ax.legend()
        plt.show()
        #return fig
    
    return print(f"Estimated compensation voltage for axis {axis}: {best_center:.3f} V")