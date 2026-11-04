# AOD uniformity optimization report

**Run:** 2026-11-04, starting at 15:43:16 UTC  
**Hardware:** 25 tones, 95–105 MHz; AWG CH0, 50-ohm load; camera serial 33834.  
**Result:** All 25 mean fitted intensities were within **0.788% of their array mean**, independently verified with **10 fresh images**. RMS nonuniformity was **0.423%**.

This is the verified optimized setting found in this run, not a claim of a global mathematical optimum or indefinite long-term stability.

## Initial versus final

All measurements below used **150 µs exposure**, unchanged camera gain index **0**, and the same image-analysis method. The original and safe-reference measurements used 3 frames each; final verification used 10 frames.

| Metric | Original equal amplitudes ≈1.0 | Safe equal-amplitude reference, 0.65 | Final optimized |
|---|---:|---:|---:|
| Mean fitted intensity (camera counts) | 107.202 | 81.079 | **77.094** |
| Lowest spot mean (counts) | 82.686 | 66.815 | **76.487** |
| Highest spot mean (counts) | 131.464 | 95.569 | **77.661** |
| RMS nonuniformity, std(I)/mean(I) | 10.571% | 8.750% | **0.423%** |
| Maximum deviation, max(abs(I/mean(I) − 1)) | 22.869% | 17.872% | **0.788%** |
| Predicted average RF power into 50 Ω | −0.458 dBm | −4.199 dBm | **−4.167 dBm** |

RMS nonuniformity improved by approximately **25×** relative to the original distribution. The mean intensity was intentionally allowed to decrease: the original waveform was above the current signal-generator configuration's −2 dBm limit, whereas all newly applied optimization waveforms stayed below it. This is therefore not a fixed-total-optical-power comparison.

![Uniformity, final amplitudes and convergence](uniformity_report.png)

![Absolute initial and final intensity](absolute_intensity_comparison.png)

## Important measured mapping correction

The initial stated ordering was tested rather than assumed after the first updates worsened uniformity.

- Reducing the **95 MHz** tone amplitude by **4%** reduced the **rightmost raw-camera spot** by **7.29%**, after normalizing out the common intensity change.
- Reducing the **105 MHz** tone amplitude by **4%** reduced the **leftmost raw-camera spot** by **7.57%**.
- Thus, for the raw arrays used by `analyze_1D_tweezer_array`, **frequency decreases from left to right**.

Use:

```python
# RF tones are in ascending frequency order; analyzer spots are in increasing camera x.
TONE_TO_SPOT = np.arange(25)[::-1]
```

The apparent orientation in another display does not change this experimentally measured array mapping. The first, incorrectly mapped trial settings were rejected; their measurements remain in the history for transparency.

## Optimization method

1. Preserved the original waveform and acquired three baseline images.
2. Read the live configurations. The existing AWG object retained an older 80 mV/3 dBm configuration, while the active signal generator used 60 mV/−2 dBm. Used the **60 mV base amplitude and stricter −2 dBm limit**; synchronized the AWG object's software configuration after completion.
3. Tried the previous interpolation calibration. Direct feedback with the initially stated mapping increased the error, so the run stopped at its amplitude-bound check instead of increasing drive further.
4. Verified the raw-image mapping using the two independent end-tone reductions above.
5. Restarted from equal relative amplitudes of 0.65, retaining the original phase pattern, and performed **five correctly mapped updates**:

```python
factor = np.clip((intensity_in_tone_order / intensity.mean()) ** (-0.3), 0.95, 1.05)
new_amplitudes = old_amplitudes * factor
```

6. Averaged three images for each update. The maximum measured deviations were:

| Correctly mapped updates | Maximum deviation | RMS nonuniformity |
|---:|---:|---:|
| 0 | 17.872% | 8.750% |
| 1 | 9.696% | 4.060% |
| 2 | 4.988% | 2.440% |
| 3 | 2.519% | 1.315% |
| 4 | 1.852% | 0.807% |
| 5 | 0.757% | 0.459% |
| Independent 10-frame verification | **0.788%** | **0.423%** |

7. Kept the final setting unchanged for independent verification and saved the exact DAC waveform, phases, amplitudes, images, and numerical results.

The endpoint tests show a local response of roughly 7–8% intensity change for a 4% amplitude change. This is not consistent with an exactly proportional I–A relation at that point, even though part of the multi-tone sweep may look linear. The damped empirical update converged without requiring that proportionality to be exact.

## Final applied amplitudes

**Order:** ascending frequency from 95 to 105 MHz, 25 equally spaced tones.  
**Definition:** multiply these values by the generator's **60 mV peak single-tone base amplitude**. They are voltage-amplitude settings, not intensity ratios or power multipliers.

```python
optimized_amplitudes = np.array([
    0.6738124915, 0.6780672674, 0.6599209328, 0.6756670689, 0.6975106821,
    0.7128943766, 0.7241315411, 0.6940404342, 0.6703836881, 0.6507809566,
    0.6305919789, 0.6276605737, 0.6433384479, 0.6520232086, 0.6557939849,
    0.6445074643, 0.6154422837, 0.6216280929, 0.6396800617, 0.6417297743,
    0.6480085709, 0.6092094391, 0.5885564252, 0.6041462232, 0.6298882489,
])
```

Use the full-precision values and original phases in `final_settings.json` for reproduction. The exact rational frequencies are included so that the waveform generator can reconstruct a short, phase-periodic segment without floating-point denominator problems. The uploaded samples are also saved directly in `final_waveform.npz`.

### Final hardware settings and checks

- Sample rate: **625 MHz**.
- Output range read back from hardware: **325 mV**.
- Relative-amplitude range: **0.588556–0.724132**, within the measured 0.5–0.8 interval.
- Nominal per-tone peak RF voltages: **35.313–43.448 mV** into the configured 50-ohm load.
- Predicted total average RF power from the actual DAC samples: **−4.167 dBm**, below the **−2 dBm** limit. This is an electrical calculation, not an RF power-meter measurement or a measurement after the amplifier.
- DAC peak fraction: **0.847407**, below the configured **0.85** headroom limit.
- Camera exposure: **150 µs**; gain index: **0**; sensor bit depth: **10**.
- Largest raw camera value in final verification: **204 / 1023**; no detected saturation.
- Lowest final fit R²: **0.999607**; no automatic fit-quality flags.

## Measurement precision and scope

- Final numbers describe **per-spot means over 10 fresh frames**, not a single noiseless image.
- Individual verification frames had maximum deviations ranging from **0.989% to 1.773%**.
- The largest standard error of a spot's frame-normalized intensity ratio was **0.179 percentage points**. These are repeatability estimates, not a full systematic uncertainty budget.
- A rigid image/array translation occurred during the session. Spot-matching checks removed common translation and continued to require stable relative spot positions; a misplaced peak was not accepted as a different RF tone.
- The optimized metric is the **background-subtracted fitted Gaussian peak amplitude of the transversely averaged strip**. It is not integrated spot power or optical intensity calibrated in W/m².
- Alignment, laser drift, exposure/gain changes, tone count, phase pattern, RF gain, or operating power changes may require another calibration. Long-term stability was not tested.

## Saved files

- `initial_final_per_tone.csv`: frequency, raw-camera spot index, initial/final amplitude and intensity, normalized intensity, and final standard errors.
- `final_settings.json`: full-precision settings, phases, mapping, verification statistics, and hardware parameters.
- `final_waveform.npz`: exact final DAC samples and reproduction metadata.
- `original_waveform.npz`: original samples and range before optimization.
- `initial_measurements.npz`, `final_verification_measurement.npz`: initial and final per-frame intensity arrays.
- `measurement_history.csv`: all completed measurements, including rejected initial trials and mapping tests.
- `*.tif` and matching `*.tif.json`: raw images and acquisition metadata. Existing files were not overwritten.

## State at completion

**The AWG was left running with the final optimized waveform. The live camera monitor was stopped.**

The active notebook kernel's `SG`, `outter_function`, `feedback_amplitudes`, `CH0_INITIAL_RELATIVE_AMPLITUDES`, `CH0_INITIAL_PHASES`, and `output_ranges` retain the final calibration. `optimized_intensity` contains the 10-frame mean fitted intensities in raw-camera order. Regenerate old waveform matrices before reuse.

`AWG.stop()` stops playback. The existing HOLDLAST stop mode is not a guaranteed zero-voltage interlock. No original sequence was automatically restored.
