"""Bounded literal arithmetic audit, never a substitute for source verification."""

import ast
import logging
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

log = logging.getLogger(__name__)
_CHARS = frozenset("0123456789.,+-−－×÷*/%％()（） \t\n")
_NUMBER = r"[-+−－]?\d+(?:,\d{3})*(?:\.\d+)?[%％]?"
_RESULT = re.compile(
    rf"(?P<value>{_NUMBER})\s*(?:亿元|万元|元|万亿|倍)\s*[（(]"
    r"(?P<expression>[0-9.,+−－×÷*/%％ \t-]{3,200})[）)]"
)


def _normalize(text):
    text = text.translate(
        str.maketrans({"−": "-", "－": "-", "×": "*", "÷": "/", "（": "(", "）": ")", "％": "%"})
    ).strip()
    while text.startswith("(") and text.count("(") > text.count(")"):
        text = text[1:].strip()
    while text.endswith(")") and text.count(")") > text.count("("):
        text = text[:-1].strip()
    return text


def _calculate(text):
    if len(text) > 256 or not text or any(c not in _CHARS for c in text):
        raise ValueError("arithmetic_scope_unsupported")
    source = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", _normalize(text).replace(",", ""))
    tree = ast.parse(source, mode="eval")
    if len(list(ast.walk(tree))) > 80:
        raise ValueError("arithmetic_scope_unsupported")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Decimal(ast.get_source_segment(source, node))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                value = a + b
            elif isinstance(node.op, ast.Sub):
                value = a - b
            elif isinstance(node.op, ast.Mult):
                value = a * b
            elif isinstance(node.op, ast.Div):
                value = a / b
            else:
                raise ValueError("arithmetic_operator_unsupported")
        else:
            raise ValueError("arithmetic_scope_unsupported")
        if not value.is_finite() or value.adjusted() > 100:
            raise ValueError("arithmetic_magnitude_unsupported")
        return value

    return visit(tree.body)


def check_arithmetic(text):
    """Check explicit equations and result-before-operands notation from the live report.

    Decimal displays are rounded to their written precision; integer results are
    exact. Matching arithmetic does not verify inputs, periods, units or claims.
    """
    candidates = [(m.group("expression"), m.group("value"), False) for m in _RESULT.finditer(text)]
    for match in re.finditer("[=＝≈]", text):
        left, right = match.start(), match.end()
        while left and text[left - 1] in _CHARS and match.start() - left < 257:
            left -= 1
        while right < len(text) and text[right] in _CHARS and right - match.end() < 257:
            right += 1
        if (left and (text[left - 1].isalpha() or text[left - 1] == "_")) or (
            right < len(text) and re.match(r"[A-Za-z_]", text[right])
        ):
            continue
        expression, result = _normalize(text[left : match.start()]), _normalize(
            text[match.end() : right].rstrip().rstrip(".")
        )
        if re.fullmatch(_NUMBER, expression) and not re.fullmatch(_NUMBER, result):
            expression, result = result, expression
        operation = re.search(r"[\d)）%％]\s*[+*/×÷−－-]", expression + " " + result)
        if (
            operation
            and expression
            and result
            and any(c.isdigit() for c in expression)
            and any(c.isdigit() for c in result)
        ):
            candidates.append((expression, result, match.group() == "≈"))
    rows = []
    for expression, result, approximate in candidates[:32]:
        row = {"expression": expression, "reported": result, "status": "unverified"}
        try:
            with localcontext() as context:
                context.prec = 160
                expected, actual = _calculate(expression), _calculate(result)
                display = result.rstrip("%％").replace(",", "")
                if re.fullmatch(_NUMBER, result) and ("." in display or approximate):
                    places = (len(display.split(".")[1]) if "." in display else 0) + (
                        2 if result.endswith(("%", "％")) else 0
                    )
                    expected = expected.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
                row.update(
                    expected=(
                        (format(expected * 100, "f") + "%")
                        if result.endswith(("%", "％"))
                        else format(expected, "f")
                    ),
                    status="matched" if expected == actual else "mismatch",
                )
                if approximate and not re.fullmatch(_NUMBER, result) and expected != actual:
                    row.update(
                        status="unverified", reason="arithmetic_approximation_precision_unknown"
                    )
        except (ValueError, SyntaxError, InvalidOperation, ArithmeticError, RecursionError):
            log.info("research_arithmetic_unverified")
        rows.append(row)
    if len(candidates) > 32 or len(text) > 100000:
        rows.append({"status": "unverified", "reason": "arithmetic_scope_limit"})
    return rows
