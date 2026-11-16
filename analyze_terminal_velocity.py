"""Measure a rising bubble and estimate terminal velocity from a video."""

import csv
import math
from pathlib import Path
import textwrap

import cv2
import matplotlib.pyplot as plt
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent
VIDEO_DIR = PROJECT_DIR / "Videos-and-references"
MAX_DISPLAY_WIDTH = 900
MAX_DISPLAY_HEIGHT = 650
MIN_STEADY_INTERVALS = 3
MAX_STEADY_SPEED_RELATIVE_STD = 0.15
MAX_STEADY_SPEED_RELATIVE_TREND = 0.15


def resize_for_display(image: np.ndarray) -> tuple[np.ndarray, float]:
    scale = min(
        MAX_DISPLAY_WIDTH / image.shape[1],
        MAX_DISPLAY_HEIGHT / image.shape[0],
        1.0,
    )
    size = (round(image.shape[1] * scale), round(image.shape[0] * scale))
    return cv2.resize(image, size), scale


def parse_positive_centimeters(value: str) -> float:
    cleaned = value.strip().lower()
    if cleaned.endswith("cm"):
        cleaned = cleaned[:-2].strip()
    try:
        distance = float(cleaned)
    except ValueError as error:
        raise ValueError("Enter a distance such as '10' or '10 cm'.") from error
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("The reference length must be greater than zero.")
    return distance


def calculate_bubble_radius(
    diameter_pixels: float, centimeters_per_pixel: float
) -> tuple[float, float]:
    if not math.isfinite(diameter_pixels) or diameter_pixels <= 0:
        raise ValueError("The measured bubble diameter must be greater than zero.")
    if not math.isfinite(centimeters_per_pixel) or centimeters_per_pixel <= 0:
        raise ValueError("The spatial calibration must be greater than zero.")
    diameter_cm = diameter_pixels * centimeters_per_pixel
    return diameter_cm, diameter_cm / 2


def select_reference_length(
    capture: cv2.VideoCapture, frame_count: int
) -> tuple[float, int]:
    """Select two reference endpoints in the same video frame."""
    window_name = "Calibration: select known length in video"
    trackbar_name = "Frame"
    selected_points: list[tuple[int, int]] = []
    selected_frame: int | None = None
    current_frame = 0

    def on_click(event: int, x: int, y: int, _flags: int, _data: object) -> None:
        nonlocal selected_frame
        if event == cv2.EVENT_LBUTTONDOWN and len(selected_points) < 2:
            if selected_frame is not None and current_frame != selected_frame:
                return
            if selected_frame is None:
                selected_frame = current_frame
            selected_points.append((x, y))

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_click)
    cv2.createTrackbar(trackbar_name, window_name, 0, frame_count - 1, lambda _value: None)
    try:
        while True:
            frame_index = cv2.getTrackbarPos(trackbar_name, window_name)
            current_frame = frame_index
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                raise RuntimeError(f"Could not read video frame {frame_index}.")
            display, scale = resize_for_display(frame)
            preview = display.copy()
            for point in selected_points:
                cv2.circle(preview, point, 6, (0, 0, 255), -1)
            if len(selected_points) == 2:
                cv2.line(
                    preview, selected_points[0], selected_points[1], (0, 255, 0), 2
                )
            cv2.putText(
                preview,
                "Choose a known reference length (not the bubble)",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                preview,
                "Click both endpoints; Enter accepts; R resets; Esc cancels",
                (10, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
            )
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(25) & 0xFF
            if key == ord("r"):
                selected_points.clear()
                selected_frame = None
            elif key in (10, 13) and len(selected_points) == 2:
                selected_frame = frame_index
                break
            elif key == 27:
                raise RuntimeError("Reference-length selection cancelled.")
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                raise RuntimeError("Reference-length selection cancelled.")
    finally:
        cv2.destroyAllWindows()

    assert selected_frame is not None
    original_points = [
        (round(x / scale), round(y / scale)) for x, y in selected_points
    ]
    pixel_length = math.dist(*original_points)
    if pixel_length <= 0:
        raise ValueError("Select two different reference endpoints.")
    known_length_cm = parse_positive_centimeters(
        input(
            "Known reference length between these points (cm; not the bubble): "
        )
    )
    return known_length_cm / pixel_length, selected_frame


def select_bubble_radius(
    capture: cv2.VideoCapture,
    frame_count: int,
    centimeters_per_pixel: float,
) -> tuple[float, float]:
    """Measure a bubble's horizontal diameter on a frame where it is visible."""
    window_name = "Bubble size: select left and right edges"
    trackbar_name = "Frame"
    edge_points: list[tuple[int, int]] = []
    current_scale = 1.0
    selected_frame: int | None = None
    current_frame = 0

    def on_click(event: int, x: int, y: int, _flags: int, _data: object) -> None:
        nonlocal selected_frame
        if event == cv2.EVENT_LBUTTONDOWN and len(edge_points) < 2:
            if selected_frame is not None and current_frame != selected_frame:
                return
            if selected_frame is None:
                selected_frame = current_frame
            edge_points.append((x, y))

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_click)
    cv2.createTrackbar(trackbar_name, window_name, 0, frame_count - 1, lambda _value: None)
    try:
        while True:
            frame_index = cv2.getTrackbarPos(trackbar_name, window_name)
            current_frame = frame_index
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                raise RuntimeError(f"Could not read video frame {frame_index}.")
            display, current_scale = resize_for_display(frame)
            preview = display.copy()
            for point in edge_points:
                cv2.circle(preview, point, 6, (0, 0, 255), -1)
            if len(edge_points) == 2:
                cv2.line(preview, edge_points[0], edge_points[1], (0, 255, 0), 2)
            cv2.putText(
                preview,
                "Choose a clear bubble frame; click its left and right edges",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                preview,
                "Measure the widest horizontal diameter; Enter accepts; R resets",
                (10, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
            )
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(25) & 0xFF
            if key == ord("r"):
                edge_points.clear()
                selected_frame = None
            elif key in (10, 13) and len(edge_points) == 2:
                selected_frame = frame_index
                break
            elif key == 27:
                raise RuntimeError("Bubble-radius measurement cancelled.")
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                raise RuntimeError("Bubble-radius measurement cancelled.")
    finally:
        cv2.destroyAllWindows()

    assert selected_frame is not None
    left_x = min(point[0] for point in edge_points)
    right_x = max(point[0] for point in edge_points)
    diameter_pixels = (right_x - left_x) / current_scale
    diameter_cm, radius_cm = calculate_bubble_radius(
        diameter_pixels, centimeters_per_pixel
    )
    return diameter_cm, radius_cm


def select_bubble_positions(
    capture: cv2.VideoCapture,
    frame_count: int,
    calibration_frame: int,
) -> list[tuple[int, int, int]]:
    """Collect manually clicked bubble centers, one position per video frame."""
    window_name = "Manual bubble positions"
    trackbar_name = "Frame"
    pending_clicks: list[tuple[int, int]] = []
    positions: dict[int, tuple[int, int]] = {}
    cancelled = False

    def on_click(event: int, x: int, y: int, _flags: int, _data: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            pending_clicks.append((x, y))

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_click)
    cv2.createTrackbar(
        trackbar_name, window_name, calibration_frame, frame_count - 1, lambda _value: None
    )
    try:
        while True:
            frame_index = cv2.getTrackbarPos(trackbar_name, window_name)
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                raise RuntimeError(f"Could not read video frame {frame_index}.")
            display, scale = resize_for_display(frame)

            if pending_clicks:
                click_x, click_y = pending_clicks.pop(0)
                positions[frame_index] = (
                    round(click_x / scale),
                    round(click_y / scale),
                )

            preview = display.copy()
            if frame_index in positions:
                x, y = positions[frame_index]
                cv2.circle(
                    preview,
                    (round(x * scale), round(y * scale)),
                    7,
                    (0, 0, 255),
                    2,
                )
            cv2.putText(
                preview,
                f"Frame {frame_index}/{frame_count - 1} | positions: {len(positions)}",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (0, 255, 255),
                2,
            )
            cv2.putText(
                preview,
                "Seek and click bubble center in each frame; N/B: +/-1, F: +10",
                (10, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
            )
            cv2.putText(
                preview,
                "Q or close window: save | R: clear | Esc: cancel",
                (10, 78),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
            )
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(25) & 0xFF
            if key == ord("q"):
                break
            if key == 27:
                cancelled = True
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("r"):
                positions.clear()
                pending_clicks.clear()
            elif key == ord("n"):
                cv2.setTrackbarPos(
                    trackbar_name, window_name, min(frame_index + 1, frame_count - 1)
                )
            elif key == ord("b"):
                cv2.setTrackbarPos(trackbar_name, window_name, max(frame_index - 1, 0))
            elif key == ord("f"):
                cv2.setTrackbarPos(
                    trackbar_name, window_name, min(frame_index + 10, frame_count - 1)
                )
    finally:
        cv2.destroyAllWindows()

    if cancelled:
        raise RuntimeError("Bubble-position selection cancelled; no results saved.")
    if len(positions) < 3:
        raise ValueError("Select the bubble center in at least three frames.")
    return [(frame, x, y) for frame, (x, y) in sorted(positions.items())]


def calculate_measurements(
    positions: list[tuple[int, int, int]],
    fps: float,
    centimeters_per_pixel: float,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    float,
    float,
    float,
    float,
    int,
    int,
]:
    frames = np.asarray([point[0] for point in positions], dtype=float)
    y_pixels = np.asarray([point[2] for point in positions], dtype=float)
    times = frames / fps
    rise_cm = (y_pixels[0] - y_pixels) * centimeters_per_pixel
    interval_times = (times[:-1] + times[1:]) / 2
    interval_velocities = np.diff(rise_cm) / np.diff(times)

    steady_interval_count = 0
    for window_size in range(
        MIN_STEADY_INTERVALS, len(interval_velocities) + 1
    ):
        candidate = interval_velocities[-window_size:]
        mean_speed = float(np.mean(candidate))
        if mean_speed <= 0:
            continue
        relative_std = float(np.std(candidate, ddof=1) / mean_speed)
        candidate_times = interval_times[-window_size:]
        velocity_slope = float(np.polyfit(candidate_times, candidate, 1)[0])
        relative_trend = (
            abs(velocity_slope)
            * float(candidate_times[-1] - candidate_times[0])
            / mean_speed
        )
        if (
            relative_std <= MAX_STEADY_SPEED_RELATIVE_STD
            and relative_trend <= MAX_STEADY_SPEED_RELATIVE_TREND
        ):
            steady_interval_count = window_size
    if steady_interval_count == 0:
        raise ValueError(
            "Could not detect a steady-speed tail: no final set of at least "
            f"{MIN_STEADY_INTERVALS} intervals has relative speed variation "
            f"and trend at or below "
            f"{MAX_STEADY_SPEED_RELATIVE_STD:.0%}. Select more "
            "positions, including several after the bubble reaches steady speed."
        )

    steady_start_index = len(positions) - steady_interval_count - 1
    fit_times = times[steady_start_index:]
    fit_positions = rise_cm[steady_start_index:]
    slope, intercept = np.polyfit(fit_times, fit_positions, 1)
    fit_residuals = fit_positions - (slope * fit_times + intercept)
    residual_sum_squares = float(np.sum(fit_residuals**2))
    total_variation = float(np.sum((fit_positions - fit_positions.mean()) ** 2))
    r_squared = (
        1.0 - residual_sum_squares / total_variation if total_variation else 0.0
    )
    standard_error = float(
        np.sqrt(
            residual_sum_squares
            / (len(fit_times) - 2)
            / np.sum((fit_times - fit_times.mean()) ** 2)
        )
    )
    return (
        times,
        rise_cm,
        interval_times,
        interval_velocities,
        float(slope),
        standard_error,
        r_squared,
        float(np.sqrt(np.mean(fit_residuals**2))),
        int(frames[steady_start_index]),
        int(frames[-1]),
    )


def unique_output_base(video_path: Path) -> Path:
    base = video_path.with_name(f"{video_path.stem}_bubble_analysis")
    suffix = 2
    while any(
        base.with_name(f"{base.name}_{suffix}{ending}").exists()
        for ending in (".csv", "_position_time.png", "_velocity_time.png")
    ) or any(
        base.with_name(f"{base.name}{ending}").exists()
        for ending in (".csv", "_position_time.png", "_velocity_time.png")
    ):
        base = video_path.with_name(f"{video_path.stem}_bubble_analysis_{suffix}")
        suffix += 1
    return base


def save_results(
    video_path: Path,
    positions: list[tuple[int, int, int]],
    centimeters_per_pixel: float,
    bubble_diameter_cm: float,
    bubble_radius_cm: float,
    times: np.ndarray,
    rise_cm: np.ndarray,
    interval_times: np.ndarray,
    interval_velocities: np.ndarray,
    terminal_velocity: float,
    velocity_error: float,
    r_squared: float,
    position_uncertainty_cm: float,
    steady_start_frame: int,
    steady_end_frame: int,
) -> tuple[Path, Path, Path]:
    base = unique_output_base(video_path)
    csv_path = base.with_suffix(".csv")
    position_plot_path = base.with_name(f"{base.name}_position_time.png")
    velocity_plot_path = base.with_name(f"{base.name}_velocity_time.png")

    with csv_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(
            [
                "frame",
                "time_s",
                "x_px",
                "y_px",
                "rise_cm",
                "position_uncertainty_cm",
                "interval_velocity_time_s",
                "interval_velocity_cm_s",
                "cm_per_pixel",
                "bubble_diameter_cm",
                "bubble_radius_cm",
                "bubble_radius_uncertainty_cm",
                "terminal_velocity_cm_s",
                "terminal_velocity_uncertainty_cm_s",
                "steady_start_frame",
                "steady_end_frame",
                "steady_region_r_squared",
            ]
        )
        for index, (frame, x, y) in enumerate(positions):
            velocity = (
                interval_velocities[index]
                if index < len(interval_velocities)
                else ""
            )
            velocity_time = (
                interval_times[index] if index < len(interval_times) else ""
            )
            writer.writerow(
                [
                    frame,
                    times[index],
                    x,
                    y,
                    rise_cm[index],
                    position_uncertainty_cm,
                    velocity_time,
                    velocity,
                    centimeters_per_pixel,
                    bubble_diameter_cm,
                    bubble_radius_cm,
                    position_uncertainty_cm,
                    terminal_velocity,
                    velocity_error,
                    steady_start_frame,
                    steady_end_frame,
                    r_squared,
                ]
            )

    frames = np.asarray([point[0] for point in positions])
    steady_mask = (frames >= steady_start_frame) & (frames <= steady_end_frame)
    fit_times = times[steady_mask]
    fit_positions = rise_cm[steady_mask]
    slope, intercept = np.polyfit(fit_times, fit_positions, 1)
    fit_line_times = np.linspace(float(fit_times.min()), float(fit_times.max()), 100)

    figure, axis = plt.subplots(figsize=(8, 5))
    axis.errorbar(
        times,
        rise_cm,
        yerr=position_uncertainty_cm,
        fmt="o",
        color="C0",
        capsize=3,
        label="Measured bubble positions",
    )
    axis.plot(
        fit_line_times,
        slope * fit_line_times + intercept,
        color="C1",
        label=f"Steady-region fit: {terminal_velocity:.3f} cm/s",
    )
    axis.axvspan(fit_times.min(), fit_times.max(), color="C1", alpha=0.1)
    axis.set(
        title=f"Bubble position vs. time — {video_path.stem}",
        xlabel="Time (s)",
        ylabel="Rise distance (cm)",
    )
    axis.grid(True, alpha=0.3)
    axis.legend()
    axis.text(
        0.02,
        0.97,
        f"Terminal velocity = {terminal_velocity:.3f} +/- {velocity_error:.3f} cm/s\n"
        f"Bubble radius = {bubble_radius_cm:.4f} +/- "
        f"{position_uncertainty_cm:.4f} cm\n"
        f"Position uncertainty = fit residual RMSE = "
        f"{position_uncertainty_cm:.4f} cm; $R^2$ = {r_squared:.4f}",
        transform=axis.transAxes,
        va="top",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
    )
    figure.tight_layout()
    figure.savefig(position_plot_path, dpi=160)
    plt.close(figure)

    frame_values = np.asarray([point[0] for point in positions])
    velocity_mask = (
        (frame_values[:-1] >= steady_start_frame)
        & (frame_values[1:] <= steady_end_frame)
    )
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(interval_times, interval_velocities, "o-", color="C2")
    axis.axhspan(
        terminal_velocity - velocity_error,
        terminal_velocity + velocity_error,
        color="C1",
        alpha=0.15,
        label="Terminal velocity uncertainty",
    )
    axis.axhline(
        slope,
        color="C1",
        linestyle="--",
        label=f"Steady-region terminal velocity: {terminal_velocity:.3f} cm/s",
    )
    if np.any(velocity_mask):
        axis.axvspan(
            interval_times[velocity_mask].min(),
            interval_times[velocity_mask].max(),
            color="C1",
            alpha=0.1,
        )
    axis.text(
        0.02,
        0.97,
        f"Terminal velocity = {terminal_velocity:.3f} +/- "
        f"{velocity_error:.3f} cm/s\n"
        f"Bubble radius = {bubble_radius_cm:.4f} +/- "
        f"{position_uncertainty_cm:.4f} cm",
        transform=axis.transAxes,
        va="top",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
    )
    axis.set(
        title=f"Bubble velocity vs. time — {video_path.stem}",
        xlabel="Time (s)",
        ylabel="Velocity (cm/s)",
    )
    axis.grid(True, alpha=0.3)
    axis.legend(loc="lower right")
    figure.tight_layout()
    figure.savefig(velocity_plot_path, dpi=160)
    plt.close(figure)
    return csv_path, position_plot_path, velocity_plot_path


def choose_video(video_files: list[Path]) -> Path:
    print("Available videos:")
    for path in video_files:
        print(f"  {path.name}")
    requested = input("Video filename: ").strip().lower()
    matches = [
        path for path in video_files if path.name.lower() == requested
    ] or [path for path in video_files if path.stem.lower() == requested]
    if len(matches) != 1:
        raise ValueError(
            "Enter one of the listed video filenames: "
            + ", ".join(path.name for path in video_files)
        )
    return matches[0]


def main() -> None:
    if not VIDEO_DIR.is_dir():
        raise FileNotFoundError(f"Video folder not found: {VIDEO_DIR}")
    video_files = sorted(
        path
        for path in VIDEO_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".avi", ".mp4", ".mov"}
    )
    if not video_files:
        raise FileNotFoundError(f"No supported videos found in {VIDEO_DIR}")
    video_path = choose_video(video_files)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or frame_count < 2:
            raise RuntimeError(f"Invalid frame rate or frame count for {video_path}")

        print(
            "\nSelect a ruler or other known length visible in the same plane as "
            "the bubble. You can move the frame slider to find it."
        )
        centimeters_per_pixel, calibration_frame = select_reference_length(
            capture, frame_count
        )
        print(f"Spatial calibration: {centimeters_per_pixel:.6f} cm/pixel")
        print(
            "\nBubble diameter is calculated from the two edge clicks using "
            "this calibration; you will not enter its length."
        )
        bubble_diameter_cm, bubble_radius_cm = select_bubble_radius(
            capture, frame_count, centimeters_per_pixel
        )
        print(
            f"Bubble diameter: {bubble_diameter_cm:.4f} cm; "
            f"radius: {bubble_radius_cm:.4f} cm"
        )
        print(
            "\nUse the frame slider or N/B/F to find the bubble. Click its center "
            "manually in each frame you want to measure. Press Q or close the "
            "window to save the selected positions."
        )
        positions = select_bubble_positions(capture, frame_count, calibration_frame)
    finally:
        capture.release()

    (
        times,
        rise_cm,
        interval_times,
        interval_velocities,
        signed_velocity,
        velocity_error,
        r_squared,
        position_uncertainty_cm,
        steady_start_frame,
        steady_end_frame,
    ) = calculate_measurements(
        positions,
        fps,
        centimeters_per_pixel,
    )
    terminal_velocity = abs(signed_velocity)
    csv_path, position_plot_path, velocity_plot_path = save_results(
        video_path,
        positions,
        centimeters_per_pixel,
        bubble_diameter_cm,
        bubble_radius_cm,
        times,
        rise_cm,
        interval_times,
        interval_velocities,
        terminal_velocity,
        velocity_error,
        r_squared,
        position_uncertainty_cm,
        steady_start_frame,
        steady_end_frame,
    )
    print(
        f"\nEstimated terminal velocity: "
        f"{terminal_velocity:.3f} +/- {velocity_error:.3f} cm/s"
    )
    print(f"Steady-region R-squared: {r_squared:.4f}")
    print(
        f"Automatically detected steady-speed frames: "
        f"{steady_start_frame} to {steady_end_frame}"
    )
    print(
        f"Position uncertainty (fit residual RMSE): "
        f"{position_uncertainty_cm:.4f} cm"
    )
    print(
        f"Bubble radius: {bubble_radius_cm:.4f} cm "
        f"+/- {position_uncertainty_cm:.4f} cm "
        f"(diameter {bubble_diameter_cm:.4f} cm)"
    )
    print(f"Saved measurements: {csv_path}")
    print(f"Saved position-time plot: {position_plot_path}")
    print(f"Saved velocity-time plot: {velocity_plot_path}")


if __name__ == "__main__":
    main()
