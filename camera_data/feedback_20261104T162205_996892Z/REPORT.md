# AOD feedback report

Camera 33834; exposure 150 µs; gain index 0.
Mapping: RF tone j maps to zero-based camera spot TONE_TO_SPOT[j], saved in final_settings.json.
Intensities are fitted peak amplitudes of the transversely averaged strip, not integrated optical powers.

| Metric | Initial (3 frames) | Verified final (10 frames) |
|---|---:|---:|
| Mean fitted intensity (counts) | 61.9679 | 60.8103 |
| RMS nonuniformity | 8.356% | 8.237% |
| Maximum deviation from mean | 17.126% | 16.229% |
| Predicted RF power (dBm) | -5.783 | -5.783 |

Verified target (1.00% maximum deviation) reached: **False**.
A completed run does not imply convergence. Uniformity can drift after verification.
Final spot means span 50.9412–70.6235 counts.
RF power is calculated from DAC samples and the output range into 50 ohms, not measured with a power meter.

![Comparison](uniformity_report.png)

Full per-tone values: initial_final_per_tone.csv. Settings/phases: final_settings.json.
Exact final samples: final_waveform.npz. Raw images and metadata are stored alongside this report.
RF left running at completion: True. Live monitor stopped; camera open/disarmed.
AWG.stop() uses the existing HOLDLAST mode and is not a guaranteed zero-voltage interlock.
