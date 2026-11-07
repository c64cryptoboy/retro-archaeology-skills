#!/usr/bin/env python3
"""Render decoded p-code as a labeled, stack-aware, human-readable listing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTROL_NAMES = {
    0x05: "WHITE", 0x11: "DOWN", 0x12: "RVS_ON", 0x13: "HOME",
    0x14: "DELETE", 0x1C: "RED", 0x1D: "RIGHT", 0x1E: "GREEN",
    0x1F: "BLUE", 0x81: "ORANGE", 0x90: "BLACK", 0x92: "RVS_OFF",
    0x93: "CLEAR", 0x95: "BROWN", 0x96: "PINK", 0x97: "DARK_GREY",
    0x98: "GREY", 0x99: "LIGHT_GREEN", 0x9A: "LIGHT_BLUE",
    0x9B: "LIGHT_GREY", 0x9C: "PURPLE", 0x9D: "LEFT",
    0x9E: "YELLOW", 0x9F: "CYAN",
}


def visible_string(text: str) -> str:
    """Turn the decoder's escaped byte string into compact PETSCII-oriented text."""
    values: list[int] = []
    index = 0
    while index < len(text):
        if text.startswith("\\x", index) and index + 4 <= len(text):
            try:
                values.append(int(text[index + 2:index + 4], 16))
                index += 4
                continue
            except ValueError:
                pass
        values.append(ord(text[index]))
        index += 1
    pieces: list[str] = []
    index = 0
    while index < len(values):
        value = values[index]
        if 0x20 <= value < 0x7F:
            pieces.append(chr(value))
            index += 1
            continue
        run = 1
        while index + run < len(values) and values[index + run] == value:
            run += 1
        name = CONTROL_NAMES.get(value, f"PETSCII_${value:02X}")
        pieces.append("{" + name + (f"*{run}" if run > 1 else "") + "}")
        index += run
    return '"' + "".join(pieces).replace('"', '\\"') + '"'


def target_name(address: int, labels: dict[int, dict[str, Any]]) -> str:
    return labels.get(address, {}).get("label", f"loc_{address:04x}")


def pop(stack: list[str], fallback: str = "<?>" ) -> str:
    return stack.pop() if stack else fallback


def basic_summary(state: dict[str, Any], text: str) -> None:
    state["_basic_summary"] = text


def explain(record: dict[str, Any], stack: list[str], labels: dict[int, dict[str, Any]], state: dict[str, Any]) -> str:
    op = record["mnemonic"]
    if op.startswith("CONST_"):
        if "text" in record:
            value = visible_string(record["text"])
        elif "exactValue" in record:
            value = record["exactValue"]
        else:
            value = str(record.get("value", "<?>"))
        stack.append(value)
        return f"push {value}"
    if op == "LOAD_VAR":
        stack.append(record["variable"])
        return f"push {record['variable']}"
    if op == "VAR_DESCRIPTOR":
        variable = record.get("variable", f"VAR_{record['variableIndex']:02X}")
        state["descriptor"] = variable
        stack.append(variable)
        return f"push extended/typed variable {variable} (also usable as a destination reference)"
    if op == "LOAD_ARRAY":
        index = pop(stack)
        value = f"{record['array']}({index})"
        stack.append(value)
        return f"replace index with {value}"
    binary = {
        "ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/",
        "POWER": "^", "AND": "AND", "OR": "OR", "EQ": "=", "NE": "<>",
        "GT": ">", "LT": "<",
    }
    if op in binary:
        right, left = pop(stack), pop(stack)
        value = f"({left} {binary[op]} {right})"
        stack.append(value)
        return f"combine top two -> {value}"
    unary = {"INT": "INT", "RND": "RND", "LEN": "LEN", "VAL": "VAL", "CHR$": "CHR$", "PEEK": "PEEK"}
    if op in unary:
        arg = pop(stack)
        value = f"{unary[op]}({arg})"
        stack.append(value)
        return f"replace top with {value}"
    if op == "MID$":
        length, start, text = pop(stack), pop(stack), pop(stack)
        value = f"MID$({text}, {start}, {length})"
        stack.append(value)
        return f"consume 3 values; push {value}"
    if op == "RIGHT$":
        length, text = pop(stack), pop(stack)
        value = f"RIGHT$({text}, {length})"
        stack.append(value)
        return f"consume 2 values; push {value}"
    if op in ("STORE_VAR", "STORE_VAR_EXT"):
        value = pop(stack)
        basic_summary(state, f"{record['variable']} = {value}")
        return f"{record['variable']} := {value}"
    if op == "STORE_ARRAY":
        value, index = pop(stack), pop(stack)
        basic_summary(state, f"{record['array']}({index}) = {value}")
        return f"{record['array']}({index}) := {value}"
    if op == "DIM_INTERNAL":
        bounds = [pop(stack) for _ in range(record["dimensions"])][::-1]
        statement = f"DIM {record['variable']}({', '.join(bounds)})"
        basic_summary(state, statement)
        return f"allocate {record['variable']}({', '.join(bounds)})"
    if op == "POKE":
        address, value = pop(stack), pop(stack)
        basic_summary(state, f"POKE {address}, {value}")
        return f"POKE {address}, {value}"
    if op in ("PRINT", "PRINT_SEMI", "PRINT_CHANNEL"):
        value = pop(stack)
        suffix = ";" if op == "PRINT_SEMI" else ""
        channel = " to selected channel" if op == "PRINT_CHANNEL" else ""
        if op == "PRINT_CHANNEL":
            selected = state.get("output_channel", "#?")
            basic_summary(state, f"PRINT#{selected}, {value}")
        else:
            basic_summary(state, f"PRINT {value}{suffix}")
        return f"output {value}{suffix}{channel}"
    if op == "PRINT_EMPTY":
        basic_summary(state, "PRINT")
        return "output newline"
    if op == "GOTO":
        stack.clear()
        target = target_name(record["target"], labels)
        basic_summary(state, f"GOTO {target}")
        return f"jump to {target}"
    if op == "GOSUB":
        target = target_name(record["target"], labels)
        basic_summary(state, f"GOSUB {target}")
        return f"call {target}"
    if op in ("IF_GOTO", "IF_FALSE_SKIP"):
        condition = pop(stack)
        target = target_name(record["target"], labels)
        if op == "IF_GOTO":
            basic_summary(state, f"IF {condition} THEN GOTO {target}")
            sense = "if true"
        else:
            basic_summary(state, f"IF NOT {condition} THEN GOTO {target}")
            sense = "if false"
        return f"{sense}: {condition} -> {target}"
    if op == "ON_GOTO":
        selector = pop(stack, state.get("descriptor", "<?>"))
        state.pop("descriptor", None)
        targets = ", ".join(target_name(value, labels) for value in record["targets"])
        basic_summary(state, f"ON {selector} GOTO {targets}")
        return f"dispatch on {selector}: {targets}"
    if op == "FOR_SETUP":
        variable = pop(stack, state.get("descriptor", "<?>"))
        end = pop(stack)
        state.pop("descriptor", None)
        basic_summary(state, f"FOR {variable} = <current value> TO {end}")
        return f"begin FOR {variable} to {end}; body follows"
    if op == "NEXT":
        variable = pop(stack, state.get("descriptor", "<?>"))
        state.pop("descriptor", None)
        target = target_name(record["target"], labels) if "target" in record else "<runtime target>"
        basic_summary(state, f"NEXT {variable}")
        return f"increment/test {variable}; repeat at {target}"
    if op == "OPEN":
        args = [pop(stack) for _ in range(record["value"])]
        statement = f"OPEN {', '.join(args)}"
        basic_summary(state, statement)
        return f"OPEN({', '.join(args)})"
    if op == "CLOSE":
        channel = pop(stack)
        basic_summary(state, f"CLOSE {channel}")
        return f"CLOSE({channel})"
    if op in ("SELECT_INPUT_CHANNEL", "SELECT_OUTPUT_CHANNEL"):
        direction = "input" if op == "SELECT_INPUT_CHANNEL" else "output"
        channel = pop(stack)
        state[f"{direction}_channel"] = channel
        return f"select {direction} channel {channel}"
    if op in ("GET", "INPUT_KEYBOARD", "READ"):
        destination = pop(stack, state.pop("descriptor", "<?>"))
        verb = {"GET": "GET", "INPUT_KEYBOARD": "INPUT", "READ": "READ"}[op]
        basic_summary(state, f"{verb} {destination}")
        return f"{verb} into {destination}"
    if op == "INPUT_BEGIN":
        state["input_fields"] = []
        return "begin INPUT statement"
    if op in ("INPUT_FIRST", "INPUT_NEXT", "INPUT_FINAL"):
        destination = pop(stack, state.pop("descriptor", "<?>"))
        state.setdefault("input_fields", []).append(destination)
        if op == "INPUT_FINAL":
            prefix = f"INPUT#{state['input_channel']}, " if "input_channel" in state else "INPUT "
            basic_summary(state, prefix + ", ".join(state.pop("input_fields")))
        return f"input field into {destination}"
    if op == "CLR_AND_INIT":
        stack.clear()
        basic_summary(state, "CLR")
        return "clear BASIC/VM state and run compiler-generated initialization p-code"
    if op == "INIT_RETURN":
        stack.clear()
        return "return from compiler-generated initialization p-code"
    if op == "RETURN":
        stack.clear()
        basic_summary(state, "RETURN")
        return "return to p-code caller"
    if op == "END":
        stack.clear()
        basic_summary(state, "END")
        return "terminate program"
    if op == "NEW":
        stack.clear()
        basic_summary(state, "NEW")
        return "erase BASIC program/state (protection failure path)"
    return ""


def render(disassembly: dict[str, Any], annotations: dict[str, Any]) -> str:
    records = disassembly["instructions"]
    custom = {int(key, 0): value for key, value in annotations.get("addresses", {}).items()}
    target_addresses = {
        target
        for record in records
        for target in ([record["target"]] if "target" in record else record.get("targets", []))
    }
    labels = {address: {"label": f"loc_{address:04x}"} for address in target_addresses}
    for address, item in custom.items():
        labels.setdefault(address, {}).update(item)

    out = [f"; {annotations.get('title', 'Annotated p-code listing')}"]
    for line in annotations.get("header", []):
        out.append(f"; {line}")
    out += [
        ";",
        "; This is postfix/stack-oriented VM code, not reconstructed BASIC.",
        "; Inline comments describe inferred stack effects and source-correlated intent.",
        "; Labels use real p-code addresses; inferred NEXT edges remain marked by the decoder.",
        "",
    ]
    glossary = annotations.get("variables", {})
    if glossary:
        out.append("; Variable glossary")
        for name in sorted(glossary):
            out.append(f";   {name:<4} {glossary[name]}")
        out.append("")

    def blank() -> None:
        if out and out[-1] != "":
            out.append("")

    def flush_pending(pending: list[tuple[str, str]], summary: str | None = None) -> None:
        if not pending:
            return
        if summary is not None:
            blank()
            out.append(f"; {summary}")
            for index, (body, comment) in enumerate(pending):
                # The BASIC-like heading already explains intermediate pushes and
                # postfix combinations. Retain only the consuming instruction's note.
                keep_comment = comment if index == len(pending) - 1 else ""
                out.append(body + (f" ; {keep_comment}" if keep_comment else ""))
        else:
            for body, comment in pending:
                out.append(body + (f" ; {comment}" if comment else ""))
        pending.clear()

    stack: list[str] = []
    state: dict[str, Any] = {}
    pending: list[tuple[str, str]] = []
    group_allowed = True
    for record in records:
        address = record["address"]
        if address in labels:
            if pending:
                flush_pending(pending)
                if stack:
                    group_allowed = False
            blank()
            item = labels[address]
            out.append(item["label"] + ":")
            for comment in item.get("comments", []):
                out.append(f"; {comment}")
        raw = record["bytes"].upper().ljust(31)
        operand = ""
        if record.get("operandKind") == "dim5":
            operand = f"{record['variable']}, dims={record['dimensions']}, desc=${record['descriptorOffset']:02X}"
        elif "variable" in record:
            operand = record["variable"]
        elif "array" in record:
            operand = record["array"]
        elif "targets" in record:
            operand = ", ".join(target_name(value, labels) for value in record["targets"])
        elif "target" in record:
            operand = target_name(record["target"], labels)
        elif "text" in record:
            operand = visible_string(record["text"])
        elif "exactValue" in record:
            operand = record["exactValue"]
        elif "value" in record:
            operand = str(record["value"])
        comment = explain(record, stack, labels, state)
        body = f"${address:04X}  {raw} {record['mnemonic']:<21} {operand:<38}".rstrip()
        pending.append((body, comment))
        summary = state.pop("_basic_summary", None)
        if summary is not None:
            clean = group_allowed and "<?>" not in summary
            flush_pending(pending, summary if clean else None)
            group_allowed = not stack
        elif record["mnemonic"] in ("INIT_RETURN",):
            flush_pending(pending)
            group_allowed = not stack
    flush_pending(pending)
    out += ["", f"; Final linear-pass expression stack depth: {len(stack)}"]
    if stack:
        out.append("; Residual expressions (linear rendering crosses CFG joins): " + ", ".join(stack))
    out.append("; Decoder diagnostics")
    for item in disassembly.get("diagnostics", []):
        out.append("; " + json.dumps(item, sort_keys=True))
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disassembly", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = render(json.loads(args.disassembly.read_text()), json.loads(args.annotations.read_text()))
    args.output.write_text(result)


if __name__ == "__main__":
    main()
