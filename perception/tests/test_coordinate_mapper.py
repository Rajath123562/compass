"""
Unit tests for Coordinate & DPI Mapper (Section 10).
Tests multi-monitor topology, negative coordinates, DPI scaling transformations,
and pre-dispatch target safety validation.
"""

from perception.coordinate_mapper import CoordinateMapper
from perception.models_multimodal import BoundingBox, CoordinateSpace


def test_coordinate_mapper_virtual_screen_bounds():
    """Verify virtual screen bounds are retrieved and valid."""
    mapper = CoordinateMapper()
    bounds = mapper.get_virtual_screen_bounds()
    assert bounds.is_valid is True
    assert bounds.width > 0
    assert bounds.height > 0
    assert bounds.coordinate_space == CoordinateSpace.SCREEN_PHYSICAL


def test_coordinate_mapper_monitors_enumeration():
    """Verify monitor enumeration returns at least one monitor with valid DPI/scale."""
    mapper = CoordinateMapper()
    monitors = mapper.get_monitors()
    assert len(monitors) >= 1

    primary_found = any(m.is_primary for m in monitors)
    assert primary_found is True

    for m in monitors:
        assert m.bounds.is_valid is True
        assert m.dpi >= 96
        assert m.scale_factor >= 1.0


def test_coordinate_space_transformation():
    """Verify coordinate transformation between Physical, Logical DPI, and Window-Relative spaces."""
    mapper = CoordinateMapper()

    # Box in physical pixels: (150, 150) to (250, 250)
    phys_box = BoundingBox(
        left=150,
        top=150,
        right=250,
        bottom=250,
        coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
    )

    # 1. Physical -> Logical DPI with 1.25x scaling (120 DPI)
    dpi_box = mapper.transform_box(
        phys_box, target_space=CoordinateSpace.SCREEN_LOGICAL_DPI, dpi_scale=1.25
    )
    assert dpi_box.coordinate_space == CoordinateSpace.SCREEN_LOGICAL_DPI
    assert dpi_box.left == int(150 / 1.25)
    assert dpi_box.width == int(100 / 1.25)

    # 2. Logical DPI -> Physical
    restored_phys = mapper.transform_box(
        dpi_box, target_space=CoordinateSpace.SCREEN_PHYSICAL, dpi_scale=1.25
    )
    assert restored_phys.coordinate_space == CoordinateSpace.SCREEN_PHYSICAL
    assert abs(restored_phys.left - phys_box.left) <= 1

    # 3. Physical -> Window Relative
    window_bounds = BoundingBox.from_ltwh(100, 100, 500, 400)
    win_box = mapper.transform_box(
        phys_box,
        target_space=CoordinateSpace.WINDOW_RELATIVE,
        window_bounds=window_bounds,
    )
    assert win_box.coordinate_space == CoordinateSpace.WINDOW_RELATIVE
    assert win_box.left == 50  # 150 - 100
    assert win_box.top == 50  # 150 - 100
    assert win_box.width == 100


def test_negative_monitor_coordinates_handling():
    """Verify multi-monitor configurations with negative coordinate offsets (Section 10)."""
    mapper = CoordinateMapper()  # noqa: F841

    # Simulate secondary monitor to the left: bounds (-1920, 0) to (0, 1080)
    neg_box = BoundingBox(
        left=-500,
        top=200,
        right=-300,
        bottom=250,
        coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
    )
    assert neg_box.left == -500
    assert neg_box.width == 200
    assert neg_box.is_valid is True
    assert neg_box.center == (-400, 225)
    assert neg_box.contains_point(-400, 225) is True
    assert neg_box.contains_point(100, 225) is False


def test_target_point_validation():
    """Verify target coordinate validation prevents clicks out of bounds or outside windows."""
    mapper = CoordinateMapper()
    vscreen = mapper.get_virtual_screen_bounds()

    # Point well inside virtual screen
    valid_pt = vscreen.center
    ok, msg = mapper.validate_target_point(*valid_pt)
    assert ok is True
    assert msg == "Valid"

    # Out of bounds point
    invalid_pt = (vscreen.right + 5000, vscreen.bottom + 5000)
    ok, msg = mapper.validate_target_point(*invalid_pt)
    assert ok is False
    assert "outside virtual screen" in msg

    # Target point inside window vs outside window
    win_box = BoundingBox.from_ltwh(100, 100, 400, 300)
    ok, msg = mapper.validate_target_point(200, 200, expected_window_bounds=win_box)
    assert ok is True

    ok, msg = mapper.validate_target_point(50, 50, expected_window_bounds=win_box)
    assert ok is False
    assert "outside expected window bounds" in msg
