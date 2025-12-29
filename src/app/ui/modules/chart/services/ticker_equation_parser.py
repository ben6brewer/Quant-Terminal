from __future__ import annotations

import re
from typing import List, Tuple, Union

import numpy as np
import pandas as pd

from app.services.market_data import fetch_price_history
from app.core.config import (
    EQUATION_OPERATORS,
    EQUATION_PREFIX,
    DEFAULT_PERIOD,
    ERROR_INVALID_EXPRESSION,
    ERROR_NO_OVERLAPPING_DATES,
)


class TickerEquationParser:
    """
    Parse and evaluate ticker equations.
    
    Examples:
        =BTC-USD*2
        =BTC-USD/SPX
        =BTC-USD + ETH-USD
        =(BTC-USD + ETH-USD)/2
    """

    def __init__(self):
        self._ticker_cache = {}

    def is_equation(self, text: str) -> bool:
        """
        Check if input is an equation.
        An equation either:
        1. Starts with =
        2. Contains operators (/, *, +) or parentheses
        3. Contains multiple ticker-like tokens separated by operators
        """
        text = text.strip()
        
        # Explicit equation marker
        if text.startswith(EQUATION_PREFIX):
            return True
        
        # Check for operators that indicate equations
        # Look for operators that are NOT part of ticker names
        # We need to be careful with - since it appears in ticker names
        
        # Check for these clear equation indicators:
        # - Division: /
        # - Multiplication: *
        # - Parentheses: ( or )
        # - Addition at start/end or with spaces: + 
        if any(op in text for op in ['/', '*', '(', ')']):
            return True
        
        # Check for + with spaces or at boundaries
        if re.search(r'(\s\+\s|\+\s|\s\+)', text):
            return True
            
        # Check for - with spaces (to distinguish from ticker hyphens)
        # BTC-USD is a ticker, but "BTC-USD - ETH-USD" is an equation
        if re.search(r'\s-\s', text):
            return True
        
        return False

    def parse_and_evaluate(
        self, equation: str, period: str = DEFAULT_PERIOD, interval: str = "1d"
    ) -> Tuple[pd.DataFrame, str]:
        """
        Parse and evaluate a ticker equation.
        
        Returns:
            (result_dataframe, description)
        """
        equation = equation.strip()
        
        # Remove leading = if present
        if equation.startswith(EQUATION_PREFIX):
            expr = equation[1:].strip()
        else:
            expr = equation

        # Tokenize the expression
        tokens = self._tokenize(expr)

        # Extract all tickers from tokens
        tickers = [t for t in tokens if self._is_ticker(t)]

        # Fetch all ticker data
        ticker_data = {}
        for ticker in tickers:
            # Create cache key with ticker, period, and interval
            cache_key = (ticker, period, interval)
            if cache_key not in self._ticker_cache:
                self._ticker_cache[cache_key] = fetch_price_history(ticker, period, interval)
            ticker_data[ticker] = self._ticker_cache[cache_key]

        # Align dates - find common date range
        aligned_data = self._align_dates(ticker_data)

        # Evaluate the expression
        result = self._evaluate_expression(tokens, aligned_data)

        # Create description
        description = f"{EQUATION_PREFIX}{expr}"

        return result, description

    def _tokenize(self, expr: str) -> List[str]:
        """
        Tokenize the expression into tickers, operators, numbers, and parentheses.
        
        Strategy: 
        - Numbers: integers or floats
        - Operators: +, -, *, /
        - Parentheses: (, )
        - Tickers: everything else (uppercase alphanumeric with hyphens)
        """
        tokens = []
        current = ""

        i = 0
        while i < len(expr):
            char = expr[i]

            # Skip whitespace
            if char.isspace():
                if current:
                    tokens.append(current)
                    current = ""
                i += 1
                continue

            # Parentheses
            if char in "()":
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
                i += 1
                continue

            # Operators - but be careful with minus in ticker names
            if char in EQUATION_OPERATORS:
                # Look ahead and behind to determine if this is an operator
                # or part of a ticker name
                if char == "-":
                    # If we have a current token and next char is alphanumeric,
                    # this might be part of a ticker like BTC-USD
                    if current and i + 1 < len(expr) and expr[i + 1].isalnum():
                        current += char
                        i += 1
                        continue

                # It's an operator
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
                i += 1
                continue

            # Build up the current token
            current += char
            i += 1

        if current:
            tokens.append(current)

        return tokens

    def _is_ticker(self, token: str) -> bool:
        """Check if a token is a ticker symbol."""
        if not token:
            return False
        # Tickers are uppercase with possible hyphens
        # and not operators or parentheses
        if token in EQUATION_OPERATORS or token in "()":
            return False
        # Check if it's a number
        try:
            float(token)
            return False
        except ValueError:
            pass
        # Must contain at least one letter
        return any(c.isalpha() for c in token)

    def _is_number(self, token: str) -> bool:
        """Check if token is a number."""
        try:
            float(token)
            return True
        except ValueError:
            return False

    def _align_dates(self, ticker_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """
        Align all tickers to common date range AND common timestamps.
        Uses inner join to ensure all tickers have exactly the same dates.
        """
        if not ticker_data:
            return {}

        if len(ticker_data) == 1:
            # Only one ticker, no alignment needed
            return ticker_data

        # Get the intersection of all indices
        common_index = None
        for df in ticker_data.values():
            if common_index is None:
                common_index = df.index
            else:
                # Get intersection of indices
                common_index = common_index.intersection(df.index)

        if len(common_index) == 0:
            raise ValueError(ERROR_NO_OVERLAPPING_DATES)

        # Reindex all dataframes to common index
        aligned = {}
        for ticker, df in ticker_data.items():
            aligned[ticker] = df.loc[common_index].copy()

        return aligned

    def _evaluate_expression(
        self, tokens: List[str], ticker_data: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Evaluate the tokenized expression.
        Computes OHLC values by evaluating the expression for each price type.
        """
        # Get sample dataframe for index
        sample_df = next(iter(ticker_data.values()))
        result_df = pd.DataFrame(index=sample_df.index)

        # Evaluate expression for each OHLC component
        for price_type in ["Open", "High", "Low", "Close"]:
            # Convert to RPN
            rpn = self._infix_to_rpn(tokens)
            
            # Evaluate RPN for this price type
            stack = []
            
            for token in rpn:
                if self._is_ticker(token):
                    # Push ticker data for this price type
                    df = ticker_data[token]
                    if price_type in df.columns:
                        stack.append(df[price_type].values)
                    else:
                        # Fallback to Close if price type doesn't exist
                        stack.append(df["Close"].values)

                elif self._is_number(token):
                    # Push number as constant
                    stack.append(float(token))

                elif token in EQUATION_OPERATORS:
                    # Pop two operands and apply operator
                    if len(stack) < 2:
                        raise ValueError(f"{ERROR_INVALID_EXPRESSION}: not enough operands for {token}")

                    b = stack.pop()
                    a = stack.pop()

                    if token == "+":
                        result = self._add(a, b)
                    elif token == "-":
                        result = self._subtract(a, b)
                    elif token == "*":
                        result = self._multiply(a, b)
                    elif token == "/":
                        result = self._divide(a, b)
                    else:
                        raise ValueError(f"Unknown operator: {token}")

                    stack.append(result)

            if len(stack) != 1:
                raise ValueError(ERROR_INVALID_EXPRESSION)

            # Get the result for this price type
            result_values = stack[0]
            
            # Handle both array and scalar results
            if isinstance(result_values, np.ndarray):
                result_df[price_type] = result_values
            else:
                result_df[price_type] = result_values

        return result_df

    def _infix_to_rpn(self, tokens: List[str]) -> List[str]:
        """Convert infix notation to Reverse Polish Notation (RPN)."""
        output = []
        operator_stack = []

        precedence = {"+": 1, "-": 1, "*": 2, "/": 2}

        for token in tokens:
            if self._is_ticker(token) or self._is_number(token):
                output.append(token)
            elif token == "(":
                operator_stack.append(token)
            elif token == ")":
                while operator_stack and operator_stack[-1] != "(":
                    output.append(operator_stack.pop())
                if operator_stack and operator_stack[-1] == "(":
                    operator_stack.pop()
            elif token in EQUATION_OPERATORS:
                while (
                    operator_stack
                    and operator_stack[-1] != "("
                    and operator_stack[-1] in precedence
                    and precedence[operator_stack[-1]] >= precedence[token]
                ):
                    output.append(operator_stack.pop())
                operator_stack.append(token)

        while operator_stack:
            output.append(operator_stack.pop())

        return output

    # Arithmetic operations that handle both arrays and scalars
    def _add(self, a: Union[np.ndarray, float], b: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        return a + b

    def _subtract(self, a: Union[np.ndarray, float], b: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        return a - b

    def _multiply(self, a: Union[np.ndarray, float], b: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        return a * b

    def _divide(self, a: Union[np.ndarray, float], b: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        # Handle division by zero
        if isinstance(b, np.ndarray):
            return np.divide(a, b, out=np.full_like(a, np.nan, dtype=float), where=b != 0)
        else:
            if b == 0:
                if isinstance(a, np.ndarray):
                    return np.full_like(a, np.nan, dtype=float)
                return np.nan
            return a / b

    def clear_cache(self):
        """Clear the ticker data cache."""
        self._ticker_cache.clear()