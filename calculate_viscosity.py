"""Calculate fluid viscosity from bubble terminal speed using Stokes' law."""

import csv
import math
from pathlib import Path


GRAVITY_M_S2 = 9.80665
AIR_DENSITY_KG_M3 = 1.2
FLUIDS = ("Oil", "Water", "Glycerol")
OUTPUT_DIRECTORY = Path(__file__).resolve().parent
VIDEO_DIRECTORY = OUTPUT_DIRECTORY / "Videos-and-references"
DATABASE_REQUIRED_COLUMNS = ("fluid", "density_kg_m3", "uncertainty_kg_m3")
ANALYSIS_REQUIRED_COLUMNS = (
    "bubble_radius_cm",
    "bubble_radius_uncertainty_cm",
    "terminal_velocity_cm_s",
    "terminal_velocity_uncertainty_cm_s",
)


def calculate_viscosity(
    fluid_density_kg_m3: float,
    fluid_density_uncertainty_kg_m3: float,
    bubble_radius_cm: float,
    bubble_radius_uncertainty_cm: float,
    terminal_velocity_cm_s: float,
    terminal_velocity_uncertainty_cm_s: float,
    air_density_kg_m3: float = AIR_DENSITY_KG_M3,
) -> tuple[float, float]:
    """Return viscosity and propagated standard uncertainty in Pa s.

    Uses the magnitude form of the provided Stokes relation:
    mu = 2*g*R^2*(rho_fluid - rho_air)/(9*|v_t|).
    Air density and gravity are treated as exact; other inputs are independent.
    """
    values = (
        fluid_density_kg_m3,
        fluid_density_uncertainty_kg_m3,
        bubble_radius_cm,
        bubble_radius_uncertainty_cm,
        terminal_velocity_cm_s,
        terminal_velocity_uncertainty_cm_s,
        air_density_kg_m3,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Measurements and uncertainties must be finite numbers.")
    if fluid_density_kg_m3 <= air_density_kg_m3:
        raise ValueError("Fluid density must be greater than air density (1.2 kg/m^3).")
    if bubble_radius_cm <= 0 or terminal_velocity_cm_s <= 0:
        raise ValueError("Bubble radius and terminal velocity must be greater than zero.")
    if any(
        uncertainty < 0
        for uncertainty in (
            fluid_density_uncertainty_kg_m3,
            bubble_radius_uncertainty_cm,
            terminal_velocity_uncertainty_cm_s,
        )
    ):
        raise ValueError("Measurement uncertainties cannot be negative.")

    radius_m = bubble_radius_cm / 100
    terminal_velocity_m_s = terminal_velocity_cm_s / 100
    density_difference = fluid_density_kg_m3 - air_density_kg_m3
    viscosity_pa_s = (
        2
        * GRAVITY_M_S2
        * radius_m**2
        * density_difference
        / (9 * terminal_velocity_m_s)
    )

    relative_uncertainty = math.sqrt(
        (2 * bubble_radius_uncertainty_cm / bubble_radius_cm) ** 2
        + (fluid_density_uncertainty_kg_m3 / density_difference) ** 2
        + (
            terminal_velocity_uncertainty_cm_s / terminal_velocity_cm_s
        ) ** 2
    )
    return viscosity_pa_s, viscosity_pa_s * relative_uncertainty


def read_csv_rows(path: Path, required_columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        missing_columns = set(required_columns) - set(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(
                f"{path} is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )
        rows = list(reader)
    if not rows:
        raise ValueError(f"No measurement rows found in {path}.")
    return rows


def latest_density_file() -> Path:
    density_files = list(OUTPUT_DIRECTORY.glob("fluid_density_results*.csv"))
    if not density_files:
        raise FileNotFoundError(
            f"No fluid_density_results CSV found in {OUTPUT_DIRECTORY}. "
            "Run calculate_fluid_density.py first."
        )
    return max(density_files, key=lambda path: path.stat().st_mtime)


def load_fluid_densities(path: Path) -> dict[str, tuple[float, float]]:
    rows = read_csv_rows(path, DATABASE_REQUIRED_COLUMNS)
    densities: dict[str, tuple[float, float]] = {}
    for row in rows:
        fluid = row["fluid"].strip().casefold()
        if fluid not in {name.casefold() for name in FLUIDS}:
            continue
        if fluid in densities:
            raise ValueError(f"Duplicate density result for {row['fluid']} in {path}.")
        try:
            density = float(row["density_kg_m3"])
            uncertainty = float(row["uncertainty_kg_m3"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid density values for {row['fluid']} in {path}."
            ) from error
        if not math.isfinite(density) or not math.isfinite(uncertainty):
            raise ValueError(f"Non-finite density values for {row['fluid']} in {path}.")
        densities[fluid] = (density, uncertainty)

    missing_fluids = [
        fluid for fluid in FLUIDS if fluid.casefold() not in densities
    ]
    if missing_fluids:
        raise ValueError(
            f"{path} does not contain density results for: "
            + ", ".join(missing_fluids)
        )
    return densities


def latest_analysis_file(fluid: str) -> Path:
    if not VIDEO_DIRECTORY.is_dir():
        raise FileNotFoundError(f"Video and measurement folder not found: {VIDEO_DIRECTORY}")
    analysis_files = [
        path
        for path in VIDEO_DIRECTORY.glob(f"{fluid}_bubble_analysis*.csv")
        if path.is_file()
    ]
    if not analysis_files:
        raise FileNotFoundError(
            f"No {fluid} bubble-analysis CSV found in {VIDEO_DIRECTORY}. "
            "Run analyze_terminal_velocity.py for this fluid first."
        )
    return max(analysis_files, key=lambda path: path.stat().st_mtime)


def load_analysis_measurements(path: Path) -> tuple[float, float, float, float]:
    rows = read_csv_rows(path, ANALYSIS_REQUIRED_COLUMNS)

    def consistent_value(column: str) -> float:
        try:
            values = [float(row[column]) for row in rows]
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid {column} value in {path}.") from error
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Non-finite {column} value in {path}.")
        first_value = values[0]
        if any(
            not math.isclose(value, first_value, rel_tol=1e-9, abs_tol=1e-12)
            for value in values[1:]
        ):
            raise ValueError(f"Inconsistent {column} values across rows in {path}.")
        return first_value

    return (
        consistent_value("bubble_radius_cm"),
        consistent_value("bubble_radius_uncertainty_cm"),
        consistent_value("terminal_velocity_cm_s"),
        consistent_value("terminal_velocity_uncertainty_cm_s"),
    )


def next_output_path() -> Path:
    base = OUTPUT_DIRECTORY / "viscosity_results"
    output_path = base.with_suffix(".csv")
    suffix = 2
    while output_path.exists():
        output_path = base.with_name(f"{base.name}_{suffix}.csv")
        suffix += 1
    return output_path


def print_results_table(results: list[dict[str, str | float]]) -> None:
    headers = (
        "Fluid",
        "Density (kg/m^3)",
        "Radius (cm)",
        "Terminal velocity (cm/s)",
        "Viscosity (Pa s)",
        "Viscosity (mPa s)",
    )
    rows = [
        (
            str(result["fluid"]),
            f"{result['fluid_density_kg_m3']:.4g} +/- "
            f"{result['fluid_density_uncertainty_kg_m3']:.2g}",
            f"{result['bubble_radius_cm']:.4g} +/- "
            f"{result['bubble_radius_uncertainty_cm']:.2g}",
            f"{result['terminal_velocity_cm_s']:.5g} +/- "
            f"{result['terminal_velocity_uncertainty_cm_s']:.2g}",
            f"{result['viscosity_Pa_s']:.5g} +/- "
            f"{result['viscosity_uncertainty_Pa_s']:.2g}",
            f"{result['viscosity_mPa_s']:.5g} +/- "
            f"{result['viscosity_uncertainty_mPa_s']:.2g}",
        )
        for result in results
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    header_line = " | ".join(
        header.ljust(widths[index]) for index, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    print("\nViscosity results (value +/- standard uncertainty)")
    print(header_line)
    print(separator)
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def main() -> None:
    print("Bubble-rise viscosity calculator")
    density_path = latest_density_file()
    densities = load_fluid_densities(density_path)
    print(f"Using fluid densities from: {density_path}")
    print(f"Air density is fixed at {AIR_DENSITY_KG_M3:g} kg/m^3.")
    print(
        "For positive viscosity, the program uses the magnitude of the density "
        "difference and terminal speed."
    )

    results: list[dict[str, str | float]] = []
    for fluid in FLUIDS:
        density, density_uncertainty = densities[fluid.casefold()]
        analysis_path = latest_analysis_file(fluid)
        (
            radius,
            radius_uncertainty,
            velocity,
            velocity_uncertainty,
        ) = load_analysis_measurements(analysis_path)
        velocity = abs(velocity)
        viscosity, viscosity_uncertainty = calculate_viscosity(
            density,
            density_uncertainty,
            radius,
            radius_uncertainty,
            velocity,
            velocity_uncertainty,
        )
        results.append(
            {
                "fluid": fluid,
                "fluid_density_kg_m3": density,
                "fluid_density_uncertainty_kg_m3": density_uncertainty,
                "air_density_kg_m3": AIR_DENSITY_KG_M3,
                "bubble_radius_cm": radius,
                "bubble_radius_uncertainty_cm": radius_uncertainty,
                "terminal_velocity_cm_s": velocity,
                "terminal_velocity_uncertainty_cm_s": velocity_uncertainty,
                "viscosity_Pa_s": viscosity,
                "viscosity_uncertainty_Pa_s": viscosity_uncertainty,
                "viscosity_mPa_s": viscosity * 1000,
                "viscosity_uncertainty_mPa_s": viscosity_uncertainty * 1000,
                "density_source_csv": str(density_path),
                "bubble_analysis_source_csv": str(analysis_path),
            }
        )

    print_results_table(results)
    output_path = next_output_path()
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved viscosity results for all three fluids to: {output_path}")


if __name__ == "__main__":
    main()
