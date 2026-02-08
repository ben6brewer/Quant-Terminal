"""Yield Curve Interpolation - Cubic spline and Nelson-Siegel fitting."""

from __future__ import annotations

from typing import Tuple


class YieldCurveInterpolation:
    """
    Provides interpolation methods for yield curve smoothing.

    All methods are static with lazy imports for numpy/scipy.
    """

    @staticmethod
    def interpolate_linear(
        maturities: list[float],
        yields: list[float],
        n_points: int = 200,
    ) -> Tuple[list[float], list[float]]:
        """
        Piecewise linear interpolation through the yield curve data points.

        Args:
            maturities: Tenor maturities in years
            yields: Yield values in percent
            n_points: Number of interpolated points

        Returns:
            Tuple of (x_smooth, y_smooth) arrays
        """
        import numpy as np

        x = np.array(maturities)
        y = np.array(yields)

        x_smooth = np.linspace(x.min(), x.max(), n_points)
        y_smooth = np.interp(x_smooth, x, y)

        return x_smooth.tolist(), y_smooth.tolist()

    @staticmethod
    def interpolate_cubic_spline(
        maturities: list[float],
        yields: list[float],
        n_points: int = 200,
    ) -> Tuple[list[float], list[float]]:
        """
        Fit a cubic spline through the yield curve data points.

        Args:
            maturities: Tenor maturities in years (e.g., [0.083, 0.25, ..., 30])
            yields: Yield values in percent (e.g., [4.5, 4.6, ...])
            n_points: Number of interpolated points

        Returns:
            Tuple of (x_smooth, y_smooth) arrays
        """
        import numpy as np
        from scipy.interpolate import CubicSpline

        x = np.array(maturities)
        y = np.array(yields)

        cs = CubicSpline(x, y)
        x_smooth = np.linspace(x.min(), x.max(), n_points)
        y_smooth = cs(x_smooth)

        return x_smooth.tolist(), y_smooth.tolist()

    @staticmethod
    def interpolate_nelson_siegel(
        maturities: list[float],
        yields: list[float],
        n_points: int = 200,
    ) -> Tuple[list[float], list[float]]:
        """
        Fit a Nelson-Siegel model to the yield curve.

        Model: y(t) = b0 + b1 * (1 - exp(-t/tau)) / (t/tau)
                          + b2 * ((1 - exp(-t/tau)) / (t/tau) - exp(-t/tau))

        Falls back to cubic spline if fitting fails.

        Args:
            maturities: Tenor maturities in years
            yields: Yield values in percent
            n_points: Number of interpolated points

        Returns:
            Tuple of (x_smooth, y_smooth) arrays
        """
        import numpy as np
        from scipy.optimize import curve_fit

        x = np.array(maturities)
        y = np.array(yields)

        def nelson_siegel(t, b0, b1, b2, tau):
            t_tau = t / tau
            exp_term = np.exp(-t_tau)
            factor = np.where(
                t_tau < 1e-10,
                1.0,  # Limit as t -> 0
                (1 - exp_term) / t_tau,
            )
            return b0 + b1 * factor + b2 * (factor - exp_term)

        try:
            # Initial guesses from data
            b0_init = y[-1]  # Long-term level (30Y yield)
            b1_init = y[0] - y[-1]  # Slope (short - long)
            b2_init = 2 * y[len(y) // 2] - y[0] - y[-1]  # Curvature
            tau_init = 2.0

            popt, _ = curve_fit(
                nelson_siegel,
                x,
                y,
                p0=[b0_init, b1_init, b2_init, tau_init],
                bounds=([-5, -15, -15, 0.1], [15, 15, 15, 10]),
                maxfev=5000,
            )

            x_smooth = np.linspace(x.min(), x.max(), n_points)
            y_smooth = nelson_siegel(x_smooth, *popt)

            return x_smooth.tolist(), y_smooth.tolist()

        except Exception as e:
            print(f"[YieldCurve] Nelson-Siegel fit failed ({e}), falling back to cubic spline")
            return YieldCurveInterpolation.interpolate_cubic_spline(
                maturities, yields, n_points
            )
