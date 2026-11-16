"""Calculate fluid density and propagated measurement uncertainty."""

import csv
import math
from pathlib import Path


GRAVITY_M_S2 = 9.80665
OUTPUT_DIRECTORY = Path(__file__).resolve().parent
FLUIDS = ("Oil", "Water", "Glycerol")


def calculate_density(
    reading: float,
    reading_uncertainty: float,
    syringe_reading: float,
    syringe_reading_uncertainty: float,
    volume_ml: float,
    volume_uncertainty_ml: float,
    reading_kind: str,
) -> tuple[float, float, float, float]:
    """Return density and standard uncertainty in kg/m^3 and g/cm^3.

    The reading and syringe tare are either masses in grams or weight forces in
    newtons. Their independent standard uncertainties are combined before
    propagating the net sample reading and volume uncertainty.
    """
    values = (
        reading,
        reading_uncertainty,
        syringe_reading,
        syringe_reading_uncertainty,
        volume_ml,
        volume_uncertainty_ml,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Measurements and uncertainties must be finite numbers.")
    net_reading = reading - syringe_reading
    if reading <= 0 or syringe_reading < 0 or net_reading <= 0 or volume_ml <= 0:
        raise ValueError(
            "The filled-syringe reading must exceed the non-negative syringe "
            "reading, and volume must be greater than zero."
        )
    if reading_uncertainty < 0 or syringe_reading_uncertainty < 0:
        raise ValueError("Measurement uncertainties cannot be negative.")
    if volume_uncertainty_ml < 0:
        raise ValueError("Measurement uncertainties cannot be negative.")

    volume_m3 = volume_ml * 1e-6
    net_reading_uncertainty = math.hypot(
        reading_uncertainty, syringe_reading_uncertainty
    )
    relative_uncertainty_squared = (
        (net_reading_uncertainty / net_reading) ** 2
        + (volume_uncertainty_ml / volume_ml) ** 2
    )

    if reading_kind == "mass":
        mass_kg = net_reading / 1000
        density_kg_m3 = mass_kg / volume_m3
    elif reading_kind == "force":
        density_kg_m3 = net_reading / (GRAVITY_M_S2 * volume_m3)
    else:
        raise ValueError("Reading kind must be 'mass' or 'force'.")

    uncertainty_kg_m3 = density_kg_m3 * math.sqrt(relative_uncertainty_squared)
    return (
        density_kg_m3,
        uncertainty_kg_m3,
        density_kg_m3 / 1000,
        uncertainty_kg_m3 / 1000,
    )


def read_number(prompt: str, *, allow_zero: bool = False) -> float:
    value = float(input(prompt))
    if not math.isfinite(value):
        raise ValueError("Enter a finite number.")
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "greater than zero"
        raise ValueError(f"Enter a value {qualifier}.")
    return value


def next_output_path() -> Path:
    base = OUTPUT_DIRECTORY / "fluid_density_results"
    output_path = base.with_suffix(".csv")
    suffix = 2
    while output_path.exists():
        output_path = base.with_name(f"{base.name}_{suffix}.csv")
        suffix += 1
    return output_path


def main() -> None:
    print("Fluid density calculator")
    print(
        "Enter measurements for oil, water, and glycerol. Uncertainties should "
        "be standard uncertainties."
    )
    results: list[dict[str, str | float]] = []

    for fluid_name in FLUIDS:
        print(f"\n{fluid_name}")
        reading_choice = input(
            "Measurement type — mass in grams (m) or weight force in newtons (f): "
        ).strip().lower()
        if reading_choice in {"m", "mass"}:
            reading_kind = "mass"
            reading_label = "Mass"
            reading_unit = "g"
        elif reading_choice in {"f", "force", "weight", "weight force"}:
            reading_kind = "force"
            reading_label = "Weight force"
            reading_unit = "N"
        else:
            raise ValueError("Choose mass (m) or weight force (f).")

        reading = read_number(
            f"Filled syringe {reading_label.lower()} ({reading_unit}): "
        )
        reading_uncertainty = read_number(
            f"Uncertainty in filled-syringe {reading_label.lower()} "
            f"({reading_unit}): ",
            allow_zero=True,
        )
        syringe_reading = read_number(
            f"Empty syringe {reading_label.lower()} ({reading_unit}): ",
            allow_zero=True,
        )
        syringe_reading_uncertainty = read_number(
            f"Uncertainty in empty-syringe {reading_label.lower()} "
            f"({reading_unit}): ",
            allow_zero=True,
        )
        volume_ml = read_number("Volume (mL): ")
        volume_uncertainty_ml = read_number(
            "Uncertainty in volume (mL): ",
            allow_zero=True,
        )
        density, density_uncertainty, density_g_cm3, uncertainty_g_cm3 = (
            calculate_density(
                reading,
                reading_uncertainty,
                syringe_reading,
                syringe_reading_uncertainty,
                volume_ml,
                volume_uncertainty_ml,
                reading_kind,
            )
        )

        print(
            f"{fluid_name}: density = {density:.4g} +/- "
            f"{density_uncertainty:.2g} kg/m^3 "
            f"({density_g_cm3:.5g} +/- {uncertainty_g_cm3:.2g} g/cm^3)"
        )
        results.append(
            {
                "fluid": fluid_name,
                "reading_type": reading_kind,
                "reading": reading,
                "reading_unit": reading_unit,
                "reading_uncertainty": reading_uncertainty,
                "syringe_reading": syringe_reading,
                "syringe_reading_uncertainty": syringe_reading_uncertainty,
                "net_sample_reading": reading - syringe_reading,
                "net_sample_reading_uncertainty": math.hypot(
                    reading_uncertainty, syringe_reading_uncertainty
                ),
                "volume_ml": volume_ml,
                "volume_uncertainty_ml": volume_uncertainty_ml,
                "density_kg_m3": density,
                "uncertainty_kg_m3": density_uncertainty,
                "density_g_cm3": density_g_cm3,
                "uncertainty_g_cm3": uncertainty_g_cm3,
            }
        )

    output_path = next_output_path()
    fieldnames = list(results[0])
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved density results for oil, water, and glycerol to: {output_path}")


if __name__ == "__main__":
    main()
