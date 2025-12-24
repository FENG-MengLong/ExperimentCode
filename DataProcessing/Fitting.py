"""
Lorentzian Fitting Module

This module provides functions for fitting single and multiple Lorentzian peaks
to 1D and 2D experimental data.

Main Functions:
    - fit_and_plot_1d_lorentzian: Fit multiple Lorentzian peaks to 1D data
    - process_2d_lorentzian_fitting: Process 2D data by fitting Lorentzians for each slice
    - plot_2d_lorentzian_results: Visualize 2D fitting results with peak branches

Author: Xinyu Feng
Created: 12/23/2025
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, differential_evolution
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
from matplotlib import rcParams

# Set default matplotlib parameters
rcParams['font.family'] = 'Times New Roman'
rcParams['mathtext.fontset'] = 'stix'
rcParams['axes.unicode_minus'] = False
rcParams.update({
    'font.size': 14,         # base font size
    'axes.titlesize': 14,
    'axes.labelsize': 14,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 12,   # legend a bit smaller
    'figure.titlesize': 14,
    'legend.frameon': False,
})


def fit_and_plot_1d_lorentzian(x, z, num_peaks, verbose=True, plot=True, 
                                xlabel='x', ylabel='z', show_individual_peaks=True):
    """
    Fit multiple Lorentzian peaks to 1D data and optionally plot the results.
    
    This function uses multiple fitting strategies (curve_fit, differential evolution,
    and random starts) to robustly fit an arbitrary number of Lorentzian peaks to
    experimental data.
    
    Parameters:
    -----------
    x : array-like
        Independent variable (e.g., frequency)
    z : array-like
        Dependent variable (e.g., counts)
    num_peaks : int
        Number of peaks to fit
    verbose : bool, optional
        If True, print progress information and results (default: True)
    plot : bool, optional
        If True, create and show plots (default: True)
    xlabel : str, optional
        Label for x-axis (default: 'x')
    ylabel : str, optional
        Label for y-axis (default: 'z')
    show_individual_peaks : bool, optional
        If True, plot individual peaks separately (default: True)
        
    Returns:
    --------
    results : dict or None
        Dictionary containing:
        - 'popt': fitted parameters array [A1, x01, gamma1, A2, x02, gamma2, ..., AN, x0N, gammaN, offset]
        - 'pcov': covariance matrix
        - 'r_squared': R² value
        - 'peak_params': list of dicts with peak parameters (A, x0, gamma)
        - 'param_errors': parameter uncertainties
        - 'x_fit': x values for fitted curve
        - 'z_fit': fitted curve values
        - 'z_peaks_fit': list of individual peak curves
        - 'num_peaks': number of peaks fitted
        Returns None if all fitting strategies fail.
    """
    # Define single Lorentzian function
    def lorentzian(x, A, x0, gamma):
        """
        Lorentzian function: L(x) = A / (1 + ((x - x0) / gamma)^2)
        
        Parameters:
            A: Peak amplitude
            x0: Peak center position
            gamma: Half-width at half-maximum (HWHM)
        """
        return A / (1 + ((x - x0) / gamma)**2)
    
    # Define multi-peak Lorentzian function (supports arbitrary number of peaks)
    def multi_lorentzian(x, *params):
        """
        Sum of N Lorentzian functions with a baseline offset.
        
        Parameters are packed as: [A1, x01, gamma1, A2, x02, gamma2, ..., AN, x0N, gammaN, offset]
        Number of peaks is determined from the length of params: (len(params) - 1) / 3
        """
        n_peaks = (len(params) - 1) // 3
        offset = params[-1]
        result = np.zeros_like(x) + offset
        
        for i in range(n_peaks):
            A = params[i * 3]
            x0 = params[i * 3 + 1]
            gamma = params[i * 3 + 2]
            result += lorentzian(x, A, x0, gamma)
        
        return result

    # Convert to numpy arrays
    x = np.array(x)
    z = np.array(z)
    
    # Analyze data structure first
    x_min, x_max = np.min(x), np.max(x)
    z_min, z_max = np.min(z), np.max(z)
    x_range = x_max - x_min
    z_range = z_max - z_min

    if verbose:
        print("Data Analysis:")
        print(f"Data points: {len(x)}")
        print(f"X range: [{np.min(x):.2f}, {np.max(x):.2f}]")
        print(f"Z range: [{np.min(z):.2f}, {np.max(z):.2f}]")
        print(f"Z mean: {np.mean(z):.4f}, Z std: {np.std(z):.4f}\n")
    
    # smooth data
    z_smooth = gaussian_filter1d(z, sigma=2)  # Adaptive smoothing
    
    # Find peaks in original data
    peaks1, props1 = find_peaks(z, height=np.mean(z), prominence=0.05*np.ptp(z_smooth), distance=1.5)
    
    # Find peaks in smoothed data
    peaks2, props2 = find_peaks(z_smooth, height=np.min(z) + z_range*0.1, prominence=0.05*np.ptp(z_smooth), distance=1.5)
    
    # Combine all detected features
    all_features = np.concatenate([peaks1, peaks2])
    all_prominences = np.concatenate([props1["prominences"], props2["prominences"]])
    
    # Determine number of peaks to use
    baseline_est = np.median(z)
    
    if verbose:
        print(f"Fitting {num_peaks} peaks:")
    
    # Select best N features based on prominence
    if len(all_features) >= num_peaks:
        sorted_idx = np.argsort(all_prominences)[::-1][:num_peaks]
        selected_features = all_features[sorted_idx]
        sort_order = np.argsort(x[selected_features])
        peak_indices = selected_features[sort_order]
        peak_positions = x[peak_indices]
        peak_values = z[peak_indices]
        
        # Estimate amplitudes
        peak_amplitudes = peak_values - baseline_est
        
    else:
        # Fallback: divide data into N regions and find max/min in each
        if verbose:
            print(f"Using region-based approach for {num_peaks} peaks")
        n_regions = num_peaks
        region_size = len(x) // n_regions
        peak_indices = []
        peak_amplitudes = []
        
        for i in range(n_regions):
            start_idx = i * region_size
            end_idx = (i + 1) * region_size if i < n_regions - 1 else len(x)
            region_z = z[start_idx:end_idx]
            region_x = x[start_idx:end_idx]
            
            # Find max or min (whichever is more prominent)
            max_idx = start_idx + np.argmax(region_z)
            min_idx = start_idx + np.argmin(region_z)
            
            if abs(z[max_idx] - np.mean(region_z)) > abs(z[min_idx] - np.mean(region_z)):
                peak_indices.append(max_idx)
                peak_amplitudes.append(z[max_idx] - np.mean(z))
            else:
                peak_indices.append(min_idx)
                peak_amplitudes.append(z[min_idx] - np.mean(z))
        
        peak_positions = x[peak_indices]
        peak_amplitudes = np.array(peak_amplitudes)
    
    if verbose:
        print(f"Selected {num_peaks} features at x positions: {peak_positions}")
        print(f"Estimated amplitudes: {peak_amplitudes}\n")
    
    # Estimate width, try to find FWHM for each peak
    estimated_widths = []
    
    for peak_idx in peak_indices:
        peak_val = z[peak_idx]
        
        # Find points where signal is halfway between peak and baseline
        target = baseline_est + (peak_val - baseline_est) / 2
        left_idx = peak_idx
        right_idx = peak_idx
        
        # Find left half-max point
        while left_idx > 0 and (z[left_idx] - target) * (peak_val - baseline_est) > 0:
            left_idx -= 1

        # Find right half-max point
        while right_idx < len(z) - 1 and (z[right_idx] - target) * (peak_val - baseline_est) > 0:
            right_idx += 1

        width_est = (x[right_idx] - x[left_idx]) / 2 if right_idx > left_idx else x_range * 0.02
        estimated_widths.append(width_est)
    estimated_widths = np.array(estimated_widths)
    
    # Build initial guess dynamically
    initial_guess = []
    for i in range(num_peaks):
        initial_guess.extend([
            peak_amplitudes[i], 
            peak_positions[i], 
            estimated_widths[i]
        ])
    initial_guess.append(baseline_est)  # offset
    
    if verbose:
        print("Initial guess:")
        for i in range(num_peaks):
            idx = i * 3
            print(f"Peak {i+1}: A={initial_guess[idx]:.4f}, Center={initial_guess[idx+1]:.4f}, Width={initial_guess[idx+2]:.4f}")
        print(f"Baseline: {initial_guess[-1]:.4f}\n")
    
    # Set bounds dynamically
    lower_bounds = []
    upper_bounds = []
    for i in range(num_peaks):
        lower_bounds.extend([0, x_min, x_range * 0.001])
        upper_bounds.extend([z_range * 3, x_max, x_range * 0.3])
    lower_bounds.append(z_min - z_range * 0.5)  # offset
    upper_bounds.append(z_max + z_range * 0.5)  # offset
    
    # Define objective function for optimization
    def objective(params):
        try:
            y_pred = multi_lorentzian(x, *params)
            return np.sum((z - y_pred)**2)
        except:
            return 1e10
    
    # Try multiple fitting strategies
    best_r2 = -np.inf
    best_popt = None
    best_pcov = None
    
    if verbose:
        print("Trying multiple fitting strategies:")
    
    # Strategy 1: Standard curve_fit with bounds
    try:
        popt1, pcov1 = curve_fit(
            multi_lorentzian, x, z, 
            p0=initial_guess, 
            bounds=(lower_bounds, upper_bounds),
            maxfev=100000,
            method='trf'
        )
        z_pred1 = multi_lorentzian(x, *popt1)
        ss_res1 = np.sum((z - z_pred1)**2)
        ss_tot1 = np.sum((z - np.mean(z))**2)
        r2_1 = 1 - (ss_res1 / ss_tot1)
        if verbose:
            print(f"Strategy 1 (curve_fit with bounds): R² = {r2_1:.6f}")
        if r2_1 > best_r2:
            best_r2 = r2_1
            best_popt = popt1
            best_pcov = pcov1
    except Exception as e:
        if verbose:
            print(f"Strategy 1 failed: {e}")
    
    
    # Strategy 2: Differential evolution
    try:
        result = differential_evolution(
            objective,
            bounds=list(zip(lower_bounds, upper_bounds)),
            seed=42,
            maxiter=1000,
            popsize=15,
            tol=1e-6
        )
        popt2 = result.x
        z_pred2 = multi_lorentzian(x, *popt2)
        ss_res2 = np.sum((z - z_pred2)**2)
        ss_tot2 = np.sum((z - np.mean(z))**2)
        r2_2 = 1 - (ss_res2 / ss_tot2)
        if verbose:
            print(f"Strategy 2 (differential evolution): R² = {r2_2:.6f}")
        if r2_2 > best_r2:
            best_r2 = r2_2
            best_popt = popt2
            # Refine with curve_fit
            try:
                best_popt, best_pcov = curve_fit(
                    multi_lorentzian, x, z, 
                    p0=best_popt, 
                    bounds=(lower_bounds, upper_bounds),
                    maxfev=50000
                )
                z_pred_refined = multi_lorentzian(x, *best_popt)
                ss_res_refined = np.sum((z - z_pred_refined)**2)
                ss_tot_refined = np.sum((z - np.mean(z))**2)
                best_r2 = 1 - (ss_res_refined / ss_tot_refined)
                if verbose:
                    print(f"  After refinement: R² = {best_r2:.6f}")
            except:
                pass
    except Exception as e:
        if verbose:
            print(f"Strategy 2 failed: {e}")
    
    # Strategy 3: Multiple random starts
    if best_r2 < 0.9:  # If still not good, try random starts
        if verbose:
            print("Trying random starting points...")
        for attempt in range(5):
            try:
                # Random initial guess within bounds
                random_guess = [np.random.uniform(lb, ub) for lb, ub in zip(lower_bounds, upper_bounds)]
                
                popt3, pcov3 = curve_fit(
                    multi_lorentzian, x, z, 
                    p0=random_guess, 
                    bounds=(lower_bounds, upper_bounds),
                    maxfev=50000,
                    method='trf'
                )
                z_pred3 = multi_lorentzian(x, *popt3)
                ss_res3 = np.sum((z - z_pred3)**2)
                ss_tot3 = np.sum((z - np.mean(z))**2)
                r2_3 = 1 - (ss_res3 / ss_tot3)
                if r2_3 > best_r2:
                    best_r2 = r2_3
                    best_popt = popt3
                    best_pcov = pcov3
            except:
                continue
        if verbose:
            print(f"Best from random starts: R² = {best_r2:.6f}")
    
    # Use best result
    if best_popt is not None:
        popt = best_popt
        
        # Calculate uncertainties if covariance matrix is available
        n_params = len(popt)
        if best_pcov is not None:
            try:
                param_errors = np.sqrt(np.diag(best_pcov))
            except:
                param_errors = np.zeros(n_params)
        else:
            param_errors = np.zeros(n_params)
        
        # Extract fitted parameters
        offset = popt[-1]
        peak_params = []
        for i in range(num_peaks):
            idx = i * 3
            A = popt[idx]
            x0 = popt[idx + 1]
            gamma = popt[idx + 2]
            peak_params.append({'A': A, 'x0': x0, 'gamma': gamma})
        
        # Calculate fitted curve
        x_fit = np.linspace(np.min(x), np.max(x), len(x) * 5)
        z_fit = multi_lorentzian(x_fit, *popt)
        
        # Calculate individual Lorentzian peaks
        z_peaks_fit = []
        colors = plt.cm.tab10(np.linspace(0, 1, num_peaks))
        for i, params in enumerate(peak_params):
            z_peak = lorentzian(x_fit, params['A'], params['x0'], params['gamma']) + offset
            z_peaks_fit.append(z_peak)
            
        # Print results
        if verbose:
            print(f"\nFITTED PARAMETERS ({num_peaks} peaks):")
            for i, params in enumerate(peak_params):
                idx = i * 3
                if np.any(param_errors > 0):
                    print(f"Peak {i+1}: A={params['A']:.4f}±{param_errors[idx]:.4f}, "
                          f"Center={params['x0']:.4f}±{param_errors[idx+1]:.4f}, "
                          f"Width={params['gamma']:.4f}±{param_errors[idx+2]:.4f}")
                else:
                    print(f"Peak {i+1}: A={params['A']:.4f}, Center={params['x0']:.4f}, Width={params['gamma']:.4f}")
            if np.any(param_errors > 0):
                print(f"Baseline offset: {offset:.4f}±{param_errors[-1]:.4f}")
            else:
                print(f"Baseline offset: {offset:.4f}")
            print(f"\nFit Quality:")
            print(f"R² = {best_r2:.6f}")
        
        # Plot results
        if plot:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[3, 1])
            
            # Main plot
            ax1.plot(x, z, 'o', markersize=5, label='Original data', alpha=0.5, color='black', zorder=1)
            ax1.plot(x_fit, z_fit, 'r-', linewidth=2.5, label=f'{num_peaks} Lorentzian fit', zorder=5)
            
            # Plot individual peaks
            if show_individual_peaks:
                for i, (z_peak, params, color) in enumerate(zip(z_peaks_fit, peak_params, colors)):
                    ax1.plot(x_fit, z_peak, '--', linewidth=1.5, alpha=0.7, 
                            label=f"Peak {i+1}", color=color, zorder=3)
                    # Mark peak centers
                    ax1.axvline(params['x0'], color=color, linestyle=':', alpha=0.5, linewidth=1)
            
            ax1.set_xlabel(xlabel)
            ax1.set_ylabel(ylabel)
            ax1.legend(loc='best')
            ax1.grid(True, alpha=0.3)
            ax1.set_title(f'{num_peaks} Lorentzian Fit ($R^2$ = {best_r2:.4f})')
            
            # Residual plot
            z_pred = multi_lorentzian(x, *popt)
            residuals = z - z_pred
            ax2.plot(x, residuals, 'o', markersize=2, alpha=0.5, color='gray')
            ax2.axhline(0, color='r', linestyle='-', linewidth=1)
            ax2.set_xlabel(xlabel)
            ax2.set_ylabel('Residuals')
            ax2.grid(True, alpha=0.3)
            rmse = np.sqrt(np.mean((z - z_pred)**2))
            ax2.set_title(f'Residuals (RMSE = {rmse:.4f})')
            
            plt.tight_layout()
            plt.show()
        
        # Return results
        results = {
            'popt': popt,
            'pcov': best_pcov,
            'r_squared': best_r2,
            'peak_params': peak_params,
            'param_errors': param_errors,
            'x_fit': x_fit,
            'z_fit': z_fit,
            'z_peaks_fit': z_peaks_fit,
            'num_peaks': num_peaks
        }
        return results
        
    else:
        if verbose:
            print("All fitting strategies failed!")
        return None


def process_2d_lorentzian_fitting(x, y, Z, num_peaks, verbose=False):
    """
    Process 2D data by fitting N Lorentzians for each voltage (x) value,
    then fit quadratic functions to each peak branch.
    
    This function performs 1D Lorentzian fitting on each slice of 2D data
    along the x-axis, then tracks peaks across slices to form branches,
    and finally fits quadratic functions to each branch.
    
    Parameters:
    -----------
    x : array-like
        Voltage values (1D array)
    y : array-like
        Frequency values (1D array)
    Z : array-like
        2D array with shape (len(x), len(y)) - counts at each (voltage, frequency)
    num_peaks : int
        Number of peaks to fit
    verbose : bool, optional
        If True, print progress information (default: False)
        
    Returns:
    --------
    results : dict
        Dictionary containing:
        - 'peak_centers': array of shape (len(x), num_peaks) - peak centers for each voltage
        - 'peak_amplitudes': array of shape (len(x), num_peaks) - peak amplitudes
        - 'peak_widths': array of shape (len(x), num_peaks) - peak widths
        - 'r_squared': array of shape (len(x),) - R² for each fit
        - 'quadratic_fits': list of num_peaks tuples (coeffs, r2) for quadratic fits of each branch
        - 'sorted_peaks': array of shape (len(x), num_peaks) - peaks sorted by position
        - 'num_peaks': number of peaks fitted
    """
    x = np.array(x)
    y = np.array(y)
    Z = np.array(Z)
    
    if Z.shape != (len(x), len(y)):
        raise ValueError(f"Z shape {Z.shape} does not match expected shape ({len(x)}, {len(y)})")
    
    # Storage for results - dynamically sized based on num_peaks
    peak_centers = np.full((len(x), num_peaks), np.nan)
    peak_amplitudes = np.full((len(x), num_peaks), np.nan)
    peak_widths = np.full((len(x), num_peaks), np.nan)
    r_squared = np.full(len(x), np.nan)
    
    # Fit multi Lorentzians for each voltage
    if verbose:
        print(f"Fitting {num_peaks} Lorentzians for {len(x)} voltage values")
        print("=" * 60)
    
    for i, voltage in enumerate(x):
        z_slice = Z[i, :]
        
        # Skip if all values are NaN or zero
        if np.all(np.isnan(z_slice)) or np.all(z_slice == 0):
            continue
        
        if verbose:
            print("-" * 60)
            print(f"Voltage {i+1}/{len(x)}: {voltage:.4f}\n")
        
        try:
            fit_results = fit_and_plot_1d_lorentzian(y, z_slice, num_peaks, verbose=verbose, plot=False)
            
            if fit_results is None:
                continue
            
            popt = fit_results['popt']
            
            # Extract parameters dynamically: [A1, x01, gamma1, A2, x02, gamma2, ..., AN, x0N, gammaN, offset]
            for peak_idx in range(num_peaks):
                param_idx = peak_idx * 3
                peak_centers[i, peak_idx] = popt[param_idx + 1]  # x0
                peak_amplitudes[i, peak_idx] = popt[param_idx]  # A
                peak_widths[i, peak_idx] = popt[param_idx + 2]  # gamma
            
            r_squared[i] = fit_results['r_squared']
            
            if verbose:
                print("-" * 60)
            
        except Exception as e:
            if verbose:
                print(f"Warning: Fit failed for voltage {voltage:.4f}: {e}")
                print("-" * 60)
            continue
    
    if verbose:
        print("=" * 60)
    
    # Sort peaks by position for each voltage to create branches
    sorted_peaks = np.full((len(x), num_peaks), np.nan)
    
    # Initialize branch assignment using first valid voltage
    first_valid_idx = np.where(~np.isnan(peak_centers[:, 0]))[0]
    if len(first_valid_idx) > 0:
        first_idx = first_valid_idx[0]
        initial_order = np.argsort(peak_centers[first_idx, :])
        
        # For each voltage, sort peaks and assign to branches
        for i in range(len(x)):
            if not np.any(np.isnan(peak_centers[i, :])):
                # Sort peaks by position
                sort_idx = np.argsort(peak_centers[i, :])
                sorted_peaks[i, :] = peak_centers[i, sort_idx]
            else:
                # Try to assign based on nearest neighbor
                if i > 0 and not np.any(np.isnan(sorted_peaks[i-1, :])):
                    # Use previous voltage's order as guide
                    current_centers = peak_centers[i, :]
                    if not np.any(np.isnan(current_centers)):
                        # Match each current peak to nearest previous peak
                        prev_centers = sorted_peaks[i-1, :]
                        assignment = []
                        used = []
                        for prev_center in prev_centers:
                            distances = [abs(c - prev_center) if j not in used else np.inf 
                                        for j, c in enumerate(current_centers)]
                            nearest_idx = np.argmin(distances)
                            assignment.append(nearest_idx)
                            used.append(nearest_idx)
                        sorted_peaks[i, :] = current_centers[assignment]
    
    # Fit quadratic functions to each branch
    quadratic_fits = []
    
    def quadratic(x, a, b, c):
        return a * x**2 + b * x + c
    
    for branch_idx in range(num_peaks):
        # Extract branch data (peak center vs voltage)
        branch_centers = sorted_peaks[:, branch_idx]
        valid_mask = ~np.isnan(branch_centers)
        
        if np.sum(valid_mask) < 3:  # Need at least 3 points for quadratic
            quadratic_fits.append((None, np.nan))
            continue
        
        x_valid = x[valid_mask]
        y_valid = branch_centers[valid_mask]
        
        try:
            # Fit quadratic
            quad_coeffs, quad_cov = curve_fit(quadratic, x_valid, y_valid)
            y_pred_quad = quadratic(x_valid, *quad_coeffs)
            ss_res_quad = np.sum((y_valid - y_pred_quad)**2)
            ss_tot_quad = np.sum((y_valid - np.mean(y_valid))**2)
            r2_quad = 1 - (ss_res_quad / ss_tot_quad) if ss_tot_quad > 0 else np.nan
            
            quadratic_fits.append((quad_coeffs, r2_quad))
            
        except Exception as e:
            if verbose:
                print(f"Warning: Quadratic fit failed for branch {branch_idx}: {e}")
            quadratic_fits.append((None, np.nan))
    
    results = {
        'peak_centers': peak_centers, # peak center position (len(x), num_peaks)
        'peak_amplitudes': peak_amplitudes, # peak amplitude (len(x), num_peaks)
        'peak_widths': peak_widths, # peak width (len(x), num_peaks)
        'r_squared': r_squared, # fit quality (len(x))
        'quadratic_fits': quadratic_fits, # quadratic fit coefficients and R² (num_peaks, 2)
        'sorted_peaks': sorted_peaks, # sorted peak positions (len(x), num_peaks)
        'num_peaks': num_peaks # number of peaks
    }
    
    return results


def plot_2d_lorentzian_results(x, y, Z, results, xlabel='Voltage (V)', ylabel='Frequency (kHz)', zlabel='Counts'):
    """
    Plot the 2D data with fitted peaks and quadratic fits.
    
    Creates a comprehensive 4-panel visualization showing:
    1. 2D map with peak positions and quadratic fits overlaid
    2. Peak positions vs voltage (branches)
    3. Peak amplitudes vs voltage
    4. Fit quality (R²) vs voltage
    
    Parameters:
    -----------
    x : array-like
        Voltage values
    y : array-like
        Frequency values
    Z : array-like
        2D data array
    results : dict
        Results from process_2d_lorentzian_fitting
    xlabel : str, optional
        Label for x-axis (default: 'Voltage (V)')
    ylabel : str, optional
        Label for y-axis (default: 'Frequency (kHz)')
    zlabel : str, optional
        Label for z-axis/colorbar (default: 'Counts')
    """
    def quadratic(x, a, b, c):
        return a * x**2 + b * x + c
    
    # Get number of peaks from results
    num_peaks = results['num_peaks']
    
    fig = plt.figure(figsize=(16, 10))
    
    # upper left: 2D map with peak positions overlaid
    ax1 = plt.subplot(2, 2, 1)
    im = ax1.pcolormesh(x, y, Z.T, shading='auto', cmap='viridis')
    plt.colorbar(im, ax=ax1, label=zlabel)
    
    # Plot sorted peaks for each branch - dynamically generate colors and labels
    colors = plt.get_cmap('gist_rainbow')(np.linspace(0, 1, num_peaks))
    labels = [f'Branch {i+1}' for i in range(num_peaks)]
    
    for branch_idx in range(num_peaks):
        branch_centers = results['sorted_peaks'][:, branch_idx]
        valid_mask = ~np.isnan(branch_centers)
        if np.any(valid_mask):
            ax1.plot(x[valid_mask], branch_centers[valid_mask], 
                    'o', color=colors[branch_idx], markersize=4, 
                    label=labels[branch_idx], alpha=0.7)
            
            # Plot quadratic fit if available
            quad_fit = results['quadratic_fits'][branch_idx]
            if quad_fit[0] is not None:
                x_fit = np.linspace(np.min(x[valid_mask]), np.max(x[valid_mask]), 200)
                y_fit = quadratic(x_fit, *quad_fit[0])
                ax1.plot(x_fit, y_fit, '--', color=colors[branch_idx], 
                        linewidth=2, alpha=0.8, label=f'{labels[branch_idx]} (quadratic)')
    
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)
    ax1.set_title('2D Map with Fitted Peaks and Quadratic Fits')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # upper right: Peak positions vs voltage (branches)
    ax2 = plt.subplot(2, 2, 2)
    for branch_idx in range(num_peaks):
        branch_centers = results['sorted_peaks'][:, branch_idx]
        valid_mask = ~np.isnan(branch_centers)
        if np.any(valid_mask):
            ax2.plot(x[valid_mask], branch_centers[valid_mask], 
                    'o', color=colors[branch_idx], markersize=5, 
                    label=labels[branch_idx], alpha=0.7)
            
            # Plot quadratic fit
            quad_fit = results['quadratic_fits'][branch_idx]
            if quad_fit[0] is not None:
                x_fit = np.linspace(np.min(x[valid_mask]), np.max(x[valid_mask]), 200)
                y_fit = quadratic(x_fit, *quad_fit[0])
                ax2.plot(x_fit, y_fit, '--', color=colors[branch_idx], 
                        linewidth=2, alpha=0.8)
                # Print quadratic coefficients
                a, b, c = quad_fit[0]
                r2 = quad_fit[1]
                ax2.text(0.05, 0.95 - branch_idx*0.1, 
                        f'{labels[branch_idx]}: y = {a:.2e}x² + {b:.2e}x + {c:.2e} ($R^2$={r2:.4f})',
                        transform=ax2.transAxes,
                        fontsize=9,
                        verticalalignment='top', color=colors[branch_idx])
    
    ax2.set_xlabel(xlabel)
    ax2.set_ylabel('Peak Center ' + ylabel)
    ax2.set_title('Peak Positions vs Voltage (Sorted Branches)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # bottom left: Peak amplitudes vs voltage
    ax3 = plt.subplot(2, 2, 3)
    for branch_idx in range(num_peaks):
        # Need to map sorted peaks back to original amplitudes
        branch_centers = results['sorted_peaks'][:, branch_idx]
        valid_mask = ~np.isnan(branch_centers)
        if np.any(valid_mask):
            # Find corresponding amplitudes
            amplitudes = np.full(len(x), np.nan)
            for i in range(len(x)):
                if valid_mask[i]:
                    # Find which original peak this corresponds to
                    center_val = branch_centers[i]
                    for orig_idx in range(num_peaks):
                        if abs(results['peak_centers'][i, orig_idx] - center_val) < 1e-6:
                            amplitudes[i] = results['peak_amplitudes'][i, orig_idx]
                            break
            
            ax3.plot(x[valid_mask], amplitudes[valid_mask], 
                    'o', color=colors[branch_idx], markersize=5, 
                    label=labels[branch_idx], alpha=0.7)
    
    ax3.set_xlabel(xlabel)
    ax3.set_ylabel('Peak Amplitude')
    ax3.set_title('Peak Amplitudes vs Voltage')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Bottom right: Fit quality (R²) vs voltage
    ax4 = plt.subplot(2, 2, 4)
    valid_r2 = ~np.isnan(results['r_squared'])
    ax4.plot(x[valid_r2], results['r_squared'][valid_r2], 'o-', 
            color='black', markersize=4, linewidth=1)
    ax4.axhline(0.9, color='green', linestyle='--', alpha=0.5, label='$R^2 = 0.9$')
    ax4.axhline(0.7, color='orange', linestyle='--', alpha=0.5, label='$R^2$ = 0.7')
    ax4.set_xlabel(xlabel)
    ax4.set_ylabel('$R^2$ (Fit Quality)')
    ax4.set_title('Lorentzian Fit Quality vs Voltage')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim([0, 1.1])
    
    plt.tight_layout()
    plt.show()
    
    # Print summary
    print("\n" + "="*60)
    print(f"QUADRATIC FIT SUMMARY ({num_peaks} branches)")
    print("="*60)
    for branch_idx in range(num_peaks):
        quad_fit = results['quadratic_fits'][branch_idx]
        if quad_fit[0] is not None:
            a, b, c = quad_fit[0]
            r2 = quad_fit[1]
            print(f"\nBranch {branch_idx + 1}:")
            print(f"  y = {a:.6e} x² + {b:.6e} x + {c:.6e}")
            print(f"  R² = {r2:.6f}")
        else:
            print(f"\nBranch {branch_idx + 1}: Fit failed or insufficient data")
    print("="*60)

