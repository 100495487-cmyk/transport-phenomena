# transport-phenomena

## Bubble terminal velocity analysis

The program manually measures a rising bubble in a video, converts its position
from pixels to centimeters using a known length visible in the video, calculates
the terminal velocity over the approximately constant-speed portion of the rise,
and saves position-versus-time and velocity-versus-time plots.

Run the analyzer from the project folder:

```powershell
.\.venv\Scripts\python.exe .\analyze_terminal_velocity.py
```

Choose a video filename. In the calibration window, move to a frame showing a
ruler or other known reference length in the same plane as the bubble. Click the
reference's two endpoints and press **Enter**, then enter that ruler/object
length in centimeters. This known length is needed to establish the pixel scale;
it is not the bubble diameter.

Next, move to a frame where a bubble is clearly visible. Click its left and right
edges across the widest horizontal diameter, then press **Enter**. Do not enter
a bubble length: the program converts the clicked pixel distance using the
calibration, calculates the radius as half the diameter, prints both values,
and includes them in the results CSV and position-time plot. The radius
uncertainty is estimated from the position-fit residual RMSE in the
automatically detected steady-speed interval.

In the measurement window, move to frames where the bubble is visible and click
its center manually in each frame. Use the frame slider, **N**/**B** for one frame
forward/back, or **F** for ten frames forward. Press **Q** or close the window to
save the selected points; press **R** to clear them or **Esc** to cancel.

The analyzer detects a steady-speed region automatically by checking trailing
sets of interval velocities, starting with the last three intervals and
selecting the largest final set whose relative standard deviation is at most
15% and whose linear speed trend is also at most 15% over the interval. It fits
position versus time over the detected region to estimate terminal velocity; no
frame-range input is needed. It saves one CSV containing every
measured position, interval velocity, the terminal velocity and its uncertainty,
the bubble radius and its uncertainty, and fit details. The position-time and
velocity-time plots show terminal velocity and radius with their uncertainties.
Outputs are saved in `Videos-and-references`.

The known length must be measured in the same plane as the bubble to minimize
perspective error. Select several bubble positions within the steady-speed
region for a reliable terminal-velocity estimate.

## Fluid density from mass or weight and volume

Run the separate density calculator:

```powershell
.\.venv\Scripts\python.exe .\calculate_fluid_density.py
```

The program prompts for measurements for oil, water, and glycerol, in that order.
For each fluid, choose mass in grams or weight force in newtons, then enter the
filled-syringe reading and its uncertainty, the empty-syringe tare reading and
its uncertainty, and the fluid volume and its uncertainty in mL. The calculator
subtracts the syringe reading from the filled-syringe reading and propagates the
uncertainties of both independent readings and the volume. It reports density
and its uncertainty in kg/m^3 and g/cm^3, then saves the input readings, net
sample reading, and results for all three fluids to a uniquely named
`fluid_density_results.csv` file.

The uncertainty calculation assumes independent standard uncertainties in the
filled-syringe reading, empty-syringe reading, and volume. If only an
instrument's smallest scale division is known and the reading is assumed equally
likely within that division, use the division width divided by the square root
of 12 as its standard uncertainty. For a force measurement, the program
subtracts the empty-syringe force and converts the net force to mass using
standard gravity.

## Fluid viscosity from bubble terminal velocity

Run the separate viscosity calculator:

```powershell
.\.venv\Scripts\python.exe .\calculate_viscosity.py
```

The calculator reads density and its uncertainty for oil, water, and glycerol
from the newest `fluid_density_results*.csv` file in the project folder. It
reads the radius, radius uncertainty, terminal speed, and terminal-speed
uncertainty for each fluid from the newest matching
`<Fluid>_bubble_analysis*.csv` file in `Videos-and-references`. Run the density
and bubble-analysis programs first; the viscosity calculator does not prompt
for measurements. It uses air density `1.2 kg/m^3`, calculates viscosity using
the Stokes relation shown in the lab, propagates independent input
uncertainties, and saves all three results, inputs, and source filenames to
`viscosity_results.csv` (or a numbered filename if that file already exists).
The terminal displays one aligned table in Oil, Water, Glycerol order, with
density, radius, terminal velocity, and viscosity values alongside their
standard uncertainties.

The CSVs must include the density and uncertainty columns from the density
calculator and the terminal velocity, radius, and their uncertainty columns
from the analyzer. If a required file or column is missing, the program stops
with an error describing what needs to be generated or corrected.

The uncertainty propagation treats air density and gravity as exact. For
`mu = 2 g R^2 (rho_fluid - rho_air) / (9 v_t)`, it uses
`u_mu/mu = sqrt((2 u_R/R)^2 + (u_rho/(rho_fluid-rho_air))^2 + (u_v/v_t)^2)`.
The signed form in the attached equation depends on the vertical sign convention;
the calculator uses the upward-speed magnitude and the positive liquid-minus-air
density difference so that viscosity is positive.

Before interpreting results, verify the input values and units, especially
density. Ensure the empty-syringe reading corresponds to the same syringe used
for the filled-syringe reading, and that both readings use the same units.
