import numpy as np
import matplotlib.pyplot as plt
import cv2
import pandas as pd
from datetime import datetime
import os, re, hashlib
from matplotlib import rcParams

rcParams['font.family'] = 'Times New Roman'
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



class PlotSaver:
	def __init__(self, root_dir):
		self.root_dir = root_dir

	def Plot3D(self, x, y, Z, xlabel='X', ylabel='Y', zlabel='Z', figsize = (6.4,4.8), transpose = False, cmap = "viridis", notes = None):
		"""
		Plot 2D pcolormesh in Jupyter and save only unique data to CSV.
		Each day has its own folder (YYYYMMDD), IDs start from 1.
		Avoids saving duplicate data by checking hash_log.txt.
		Even if data is duplicate, the plot still shows with ID.
		"""
	
		# --- normalize the data ---
		x, y, Z = validate_input(x,y,Z)
		
		# --- Date setup ---
		today_raw = datetime.now()
		today_display = today_raw.strftime("%Y/%m/%d") # for plot title
	
		# --- Get the save_directory ---
		save_dir, today_str = _get_save_dir(self.root_dir, today_raw) # today_str is used to read the previous id
	
	
		# --- Check hash and get id
		plot_id, data_hash, already_saved = _get_plot_id(x, y, Z, xlabel, ylabel, zlabel, save_dir, today_str)
	
	
		# --- Create title and filename ---
		title = f"{today_display}: ID {plot_id}"
		csv_filename = os.path.join(save_dir, f"{today_str}_ID{plot_id}.csv")
	 
	
		# --- plot, even if duplicate ---
		if transpose:
			_showPlot3D(y, x, Z, ylabel, xlabel, zlabel, title, figsize, cmap, notes)
		else:
			_showPlot3D(x, y, Z.T, xlabel, ylabel, zlabel, title, figsize, cmap, notes)
	
		# --- If already saved, stop the following save ---
		if already_saved:
			return
	
		# --- Save the data and hash to hash_log ---
		_save_csv(x, y, Z, xlabel, ylabel, zlabel, data_hash, plot_id, csv_filename, today_display, notes)
		
	
	
	# ----- 2D line plot with duplicate-aware saving (same policy as Plot3D) -----
	def Plot2D(self, x, y, Z, xlabel='X', ylabel='Y', zlabel='Z', figsize = (6.4,4.8), cmap = "viridis",
			   y_index=None, y_value=None, notes = None):
		"""
		Plot 2D line(s) from Z(x, y) in Jupyter and save CSV only if data is new.
		Folder structure is <root_dir>/<YYYYMMDD>/, IDs start from 1 per day.
		Duplicate detection uses _compute_data_hash(x, y, Z, xlabel, ylabel, zlabel).
		"""
		
		# --- normalize the data ---
		x, y, Z = validate_input(x,y,Z)
		
		# --- Date setup ---
		today_raw = datetime.now()
		today_display = today_raw.strftime("%Y/%m/%d") # for plot title
	
		# --- Get the save_directory ---
		save_dir, today_str = _get_save_dir(self.root_dir, today_raw) # today_str is used to read the previous id
	
	
		# --- Check hash and get id
		plot_id, data_hash, already_saved = _get_plot_id(x, y, Z, xlabel, ylabel, zlabel, save_dir, today_str)
	
	
		# --- Create title and filename ---
		title = f"{today_display}: ID {plot_id}"
		csv_filename = os.path.join(save_dir, f"{today_str}_ID{plot_id}.csv")
	 
	
		# --- plot, even if duplicate ---
		_showPlot2D(x, y, Z, xlabel, ylabel, zlabel, title, figsize, cmap, y_index, y_value, notes)
	
		# --- If already saved, stop the following save ---
		if already_saved:
			return
	
		# --- Save the data and hash to hash_log ---
		_save_csv(x, y, Z, xlabel, ylabel, zlabel, data_hash, plot_id, csv_filename, today_display, notes)


	def save_frame(
	    self,
	    frame,
	    xlabel="pixel_x",
	    ylabel="pixel_y",
	    zlabel="intensity",
	    normalize_to_uint8=False,
	    save_png=True,
	    save_csv=False,
	    figsize=(6.4, 4.8),
	    cmap="viridis",
	    notes=None,
	):
	    """
	    Save a 2D image frame using the same date-folder / ID / hash policy as Plot3D/Plot2D.
	
	    If save_csv=True, the frame is also plotted with a title.
	    Hash is recorded only when CSV is saved.
	    """
	    frame = np.asarray(frame)
	    if frame.ndim != 2:
	        raise ValueError(f"frame must be a 2D array, got shape {frame.shape}")
	
	    x = np.arange(frame.shape[1])
	    y = np.arange(frame.shape[0])
	    Z = frame.T
	
	    today_raw = datetime.now()
	    today_display = today_raw.strftime("%Y/%m/%d")
	
	    save_dir, today_str = _get_save_dir(self.root_dir, today_raw)
	
	    plot_id, data_hash, already_saved = _get_plot_id(
	        x, y, Z, xlabel, ylabel, zlabel, save_dir, today_str
	    )
	
	    title = f"{today_display}: ID {plot_id}"
	    png_filename = os.path.join(save_dir, f"{today_str}_ID{plot_id}.png")
	    csv_filename = os.path.join(save_dir, f"{today_str}_ID{plot_id}.csv")
	
	    if save_csv:
	        _showPlot3D(
	            x=x,
	            y=y,
	            Z=frame,
	            xlabel=xlabel,
	            ylabel=ylabel,
	            zlabel=zlabel,
	            title=title,
	            figsize=figsize,
	            cmap=cmap,
	            notes=notes,
	        )
			_save_csv(
	            x=x,
	            y=y,
	            Z=Z,
	            xlabel=xlabel,
	            ylabel=ylabel,
	            zlabel=zlabel,
	            data_hash=data_hash,
	            plot_id=plot_id,
	            csv_filename=csv_filename,
	            today_display=today_display,
	            notes=notes,
	        )
	
	    if already_saved:
	        return {
	            "id": plot_id,
	            "already_saved": "duplicated",
	            "png_path": png_filename if save_png else None,
	            "csv_path": csv_filename if save_csv else None,
	            "hash": data_hash,
	        }
	
	    if save_png:
	        image_to_save = frame
	        if normalize_to_uint8:
	            image_to_save = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)
	            image_to_save = image_to_save.astype(np.uint8)
	        else:
	            if image_to_save.dtype in (np.float32, np.float64):
	                image_to_save = cv2.normalize(frame, None, 0, 65535, cv2.NORM_MINMAX)
	                image_to_save = image_to_save.astype(np.uint16)
	
	        success = cv2.imwrite(str(png_filename), image_to_save)
	        if not success:
	            raise IOError(f"Failed to save image to: {png_filename}")
	        
	
	    return {
	        "id": plot_id,
	        "already_saved": "successful",
	        "png_path": png_filename if save_png else None,
	        "csv_path": csv_filename if save_csv else None,
	        "hash": data_hash,
	    }


# compute unique hash for x, y, Z, and labels
def _compute_data_hash(x, y, Z, xlabel, ylabel, zlabel):
	"""
	Compute a unique hash (SHA-256) for a dataset and its labels.
	Used to detect duplicate data so it won't be saved multiple times.
	"""
	m = hashlib.sha256()
	m.update(np.array(x).tobytes())
	m.update(np.array(y).tobytes())
	m.update(np.array(Z).tobytes())
	for s in (xlabel, ylabel, zlabel):
		m.update(s.encode('utf-8'))
	return m.hexdigest()

def _get_save_dir(root_dir, today_raw):
	"""
	Multi-level folder structure:
	root / YYYY / YYYYMMDD
	"""
	year_str = today_raw.strftime("%Y")
	month_str = today_raw.strftime("%m")
	date_str = today_raw.strftime("%d")
	today_str = today_raw.strftime("%Y%m%d")

	save_dir = os.path.join(root_dir, year_str, month_str, date_str)

	os.makedirs(save_dir, exist_ok=True)
	return save_dir, today_str  # today_str used for filenames

# Validate array shapes 
def validate_input(x,y,Z):
	
	# --- Normalize inputs ---
	x = np.array(x)

	# y is single value → wrap
	if y is None:
		pass
	elif np.isscalar(y):
		y = np.array([y])
	else:
		y = np.array(y)

	# --- Normalize Z ---
	Z = np.array(Z)

	# If Z is 1D, reshape to (1, len(x))
	if Z.ndim == 1:
		if len(Z) != len(x):
			raise ValueError("1D Z must have same length as x.")
		Z = Z.reshape(-1, 1)
	
	if y is not None and Z.shape != (len(x), len(y)):
		raise ValueError(f"Z shape {Z.shape} must be (len(x), len(y)) = ({len(x)}, {len(y)})")

	return x,y,Z

def _get_plot_id(x, y, Z, xlabel, ylabel, zlabel, save_dir, today_str):
	"""
	Compute hash, check hash_log.txt, and assign ID.
	Returns: plot_id, data_hash, already_saved (bool)
	"""
	hash_log_path = os.path.join(save_dir, "hash_log.txt")
	data_hash = _compute_data_hash(x, y, Z, xlabel, ylabel, zlabel)

	already_saved = False
	if os.path.exists(hash_log_path):
		with open(hash_log_path, 'r', encoding='utf-8') as f:
			if data_hash in f.read():
				already_saved = True

	existing_files = os.listdir(save_dir)
	pattern = re.compile(rf"{today_str}_ID(\d+)\.csv") # today_str is part of the csv filename, used to read the previous id
	ids_today = [int(m.group(1)) for f in existing_files if (m := pattern.search(f))]

	if already_saved:
		plot_id = max(ids_today, default=0)
	else:
		plot_id = max(ids_today, default=0) + 1

	return plot_id, data_hash, already_saved

# Plot function
def _showPlot3D(x, y, Z, xlabel, ylabel, zlabel, title, figsize, cmap, notes):
	width, height = figsize
	extra_bottom = 3
	fig = plt.figure(figsize=(width,height+extra_bottom))

	ax = fig.add_axes([0.12, extra_bottom/(height+extra_bottom),
                       0.78, height/(height+extra_bottom)])

	ax_notes = fig.add_axes([0.05, 0.01,
							 0.90, (extra_bottom-1)/(height+extra_bottom)])
	ax_notes.axis("off")


	mesh = ax.pcolormesh(x, y, Z, shading='auto', cmap=cmap)
	cbar = plt.colorbar(mesh, ax=ax)
	cbar.set_label(zlabel)
	ax.set_xlabel(xlabel)
	ax.set_ylabel(ylabel)
	ax.set_title(title)

	# --- display notes ---
	if notes:
		notes_text = "\n".join(f"{k}: {v}" for k, v in notes.items())
		ax_notes.text(
				0.01, 0.95,           # top-left of notes box
				notes_text,
				ha='left',
				va='top',
				fontsize=12,
		)
		
	plt.show()

def _showPlot2D(x, y, Z, xlabel, ylabel, zlabel, title, figsize, cmap, y_index, y_value, notes):
	width, height = figsize
	extra_bottom = 3
	fig = plt.figure(figsize=(width,height+extra_bottom))

	ax = fig.add_axes([0.12, extra_bottom/(height+extra_bottom),
                       0.78, height/(height+extra_bottom)])

	ax_notes = fig.add_axes([0.05, 0.01,
							 0.90, (extra_bottom-1)/(height+extra_bottom)])
	ax_notes.axis("off")   

	# --- Handle y_index as single int or (start, end) range ---
	if y_index is not None:
		if isinstance(y_index, (list, tuple)) and len(y_index) == 2:
			start, end = y_index
			start = max(0, start)
			end = min(len(y), end)
			colors = plt.get_cmap(cmap)(np.linspace(0, 1, end - start))
			for i, idx in enumerate(range(start, end)):
				ax.plot(x, Z[:, idx], color=colors[i],
						label=f"{ylabel}={y[idx]:.3g}")
		else:
			# single index
			idx = int(y_index)
			ax.plot(x, Z[:, idx], label=f"{ylabel} = {y[idx]:.3g}")

	elif y_value is not None:
		# plot nearest y-value
		idx = int(np.argmin(np.abs(y - y_value)))
		ax.plot(x, Z[:, idx], label=f"{ylabel} ≈ {y[idx]:.3g}")

	elif y is not None:
		# plot all y rows
		colors = plt.get_cmap(cmap)(np.linspace(0, 1, len(y)))
		for i in range(len(y)):
			ax.plot(x, Z[:, i], color=colors[i], label=f"{ylabel}={y[i]:.3g}")
	else:
		ax.plot(x,Z, color = plt.get_cmap(cmap)(0.0))

	# --- Labels and formatting ---
	ax.set_xlabel(xlabel)
	ax.set_ylabel(zlabel)
	ax.set_title(title)
	if y is not None:
		ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=10)

	# --- display notes ---
	if notes:
		notes_text = "\n".join(f"{k}: {v}" for k, v in notes.items())
		ax_notes.text(
				0.01, 0.95,           # top-left of notes box
				notes_text,
				ha='left',
				va='top',
				fontsize=12,
        )

	# fig.tight_layout()
	plt.show()

def _save_csv(x, y, Z, xlabel, ylabel, zlabel, data_hash, plot_id, csv_filename, today_display, notes):

	# ---- Convert notes dict to a clean string ----
	if notes is None or len(notes) == 0:
		notes_str = ""
	else:
		notes_str = "; ".join(f"{k}={v}" for k, v in notes.items())

	if y is not None:
		Y_mesh, X_mesh = np.meshgrid(y, x)
		df = pd.DataFrame({
			'x': X_mesh.ravel(),
			'y': Y_mesh.ravel(),
			'z': Z.ravel()
		})

		header_lines = [
			f"# Date: {today_display}",
			f"# ID: {plot_id}",
			f"# Data hash: {data_hash}",
			f"# xlabel: {xlabel}",
			f"# ylabel: {ylabel}",
			f"# zlabel: {zlabel}",
			f"# x range: {x[0]} to {x[-1]}, total {len(x)} points",
			f"# y range: {y[0]} to {y[-1]}, total {len(y)} points",
			f"# Notes: {notes_str}",
			"# ---------------------------------------------"
		]

	else:
		df = pd.DataFrame({
			'x': x,
			'z': Z.ravel()
		})

		header_lines = [
			f"# Date: {today_display}",
			f"# ID: {plot_id}",
			f"# Data hash: {data_hash}",
			f"# xlabel: {xlabel}",
			f"# zlabel: {zlabel}",
			f"# x range: {x[0]} to {x[-1]}, total {len(x)} points",
			f"# Notes: {notes_str}",
			"# ---------------------------------------------"
		]

	# ---- Write header ----
	with open(csv_filename, 'w', encoding='utf-8') as f:
		f.write("\n".join(header_lines) + "\n")

	# ---- Append data ----
	df.to_csv(csv_filename, mode='a', index=False)

	# ---- Append hash ----
	hash_log_path = os.path.join(os.path.dirname(csv_filename), "hash_log.txt")
	with open(hash_log_path, 'a', encoding='utf-8') as f:
		f.write(data_hash + "\n")





	