*Author: Xinyu Feng*
# Math derivation
## Estimation of the PZT response
The frequency of the laser is controlled by the PZT, but the PZT is not a linear instrument, so the output frequency can be written as the function of the voltage applied on it.
$$\begin{align*}
f &= F(V)
\end{align*}$$

For F-P cavity, the resonant peaks are noted as $f_{0m}$, $m$ represents the order of the peak. So when scanning the PZT voltage using a triangular wave, we can see a series peaks with a symmetric axis at the center.!()[assets/Pasted image 20251129183531.png]The position of the peak satisfies the $$\begin{align*}
f_{0m} &= F(V_{0m})
\end{align*}$$
We can use the peak positions and FSR to estimate the function $F$

Then we can move the stepper motors, the peaks will move with the stepper motor. For each stepper motor position, we can get an estimation of $F$, then average them.
![assets/Pasted image 20251129184303.png]
**$F$ can be linear or parabola depending on how accurate you want**

## Estimate the frequency change
After get $F$, set the step=0 as the start point, calculate the frequency changes with respect to the original point based on $F$.

## Calculate the amount of frequency change per step
After get the frequency changes, do linear fit with respect to steps and average the slopes.
**The slope is the calibration factor**
![[Pasted image 20251129185120.png]]

