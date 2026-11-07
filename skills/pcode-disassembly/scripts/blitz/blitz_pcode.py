#!/usr/bin/env python3
"""Conservative profile-driven BLITZ! p-code disassembler.

This core contains no Depths-specific addresses or opcode semantics. Those live in
an external profile. Unknown-length forms stop recursive decoding rather than
being guessed through.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class Image:
    path: Path
    load: int
    data: bytes
    sha256: str

    @property
    def end(self) -> int:
        return self.load + len(self.data)

    def contains(self, address: int, length: int = 1) -> bool:
        return self.load <= address and address + length <= self.end

    def read(self, address: int, length: int) -> bytes:
        if not self.contains(address, length):
            raise DecodeError(
                f"read ${address:04X}+{length} outside ${self.load:04X}-${self.end - 1:04X}"
            )
        start = address - self.load
        return self.data[start : start + length]


def load_prg(path: Path) -> Image:
    raw = path.read_bytes()
    if len(raw) < 3:
        raise DecodeError("PRG must contain a two-byte load address and payload")
    return Image(path, int.from_bytes(raw[:2], "little"), raw[2:], hashlib.sha256(raw).hexdigest())


def load_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text())
    if profile.get("schema") != "blitz-pcode-profile-v1":
        raise DecodeError("unsupported profile schema")
    return profile


def decode_var_name(record: bytes) -> str:
    if len(record) < 2:
        return "?"
    first, second = record[:2]
    suffix = "$" if second & 0x80 else ("%" if first & 0x80 else "")
    chars = [chr(value & 0x7F) for value in (first, second) if value & 0x7F]
    return "".join(chars) + suffix


def variable_names(image: Image, profile: dict[str, Any]) -> list[str]:
    layout = profile.get("layout", {})
    required = ("variableTable", "variableCount", "variableRecordSize")
    if not all(key in layout for key in required):
        return []
    base = int(layout["variableTable"])
    count = int(layout["variableCount"])
    size = int(layout["variableRecordSize"])
    return [decode_var_name(image.read(base + index * size, size)) for index in range(count)]


def _need(image: Image, address: int, size: int) -> bytes:
    try:
        return image.read(address, size)
    except DecodeError as exc:
        raise DecodeError(f"truncated p-code instruction at ${address:04X}: {exc}") from exc


def _operand_size(kind: str, image: Image, address: int, opcode: int) -> int:
    fixed = {
        "none": 1,
        "u8": 2,
        "argc_u8": 2,
        "skip_u8": 2,
        "index_u8": 2,
        "descriptor_u8": 2,
        "target_be16": 3,
        "u16be": 3,
        "fixed5": 6,
        "dim5": 6,
        "fac5": 6,
        "def_fn_header": 6,
    }
    if kind in fixed:
        return fixed[kind]
    if kind == "inline_basic_to_colon":
        quote = False
        for size in range(2, min(258, image.end - address + 1)):
            value = _need(image, address + size - 1, 1)[0]
            if value == 0x22:
                quote = not quote
            elif value == 0x3A and not quote:
                return size
        raise DecodeError(f"unterminated inline BASIC statement at ${address:04X}")
    if kind == "inline_string_u8":
        length = _need(image, address + 1, 1)[0]
        return 2 + length
    if kind == "inline_string_short":
        return 1 + (opcode & 0x07)
    if kind == "on_table":
        length = _need(image, address + 1, 1)[0]
        if length < 2 or (length - 2) % 2:
            raise DecodeError(f"invalid ON-table size {length} at ${address:04X}")
        return length
    raise DecodeError(f"unknown operand grammar {kind!r}")


def opcode_spec(opcode: int, profile: dict[str, Any]) -> dict[str, Any]:
    exact = profile.get("exactOpcodes", {}).get(f"{opcode:02X}")
    if exact is not None:
        return dict(exact)

    for family in profile.get("opcodeFamilies", []):
        minimum = int(str(family["minimum"]), 16)
        maximum = int(str(family["maximum"]), 16)
        if minimum <= opcode <= maximum:
            spec = {key: value for key, value in family.items() if key not in ("minimum", "maximum")}
            spec["mnemonic"] = spec["mnemonic"].replace("{opcode}", f"{opcode:02X}")
            if "variableIndexMask" in spec:
                spec["variableIndex"] = opcode & int(spec.pop("variableIndexMask"))
            if "valueMask" in spec:
                spec["value"] = opcode & int(spec.pop("valueMask"))
            return spec
    return {
        "mnemonic": f"OP_{opcode:02X}",
        "operand": "unknown",
        "confidence": "unknown",
    }


def _text_bytes(data: bytes) -> str:
    return "".join(chr(value) if 0x20 <= value < 0x7F else f"\\x{value:02x}" for value in data)


def decode_fac5(data: bytes) -> Fraction:
    if len(data) != 5:
        raise DecodeError("FAC constant must be exactly five bytes")
    exponent = data[0]
    if exponent == 0:
        return Fraction(0)
    negative = bool(data[1] & 0x80)
    fraction_bits = (
        (data[1] & 0x7F) << 24 | data[2] << 16 | data[3] << 8 | data[4]
    )
    significand = Fraction((1 << 31) + fraction_bits, 1 << 31)
    power = exponent - 129
    value = significand * (1 << power) if power >= 0 else significand / (1 << -power)
    return -value if negative else value


def decode_one(
    image: Image, profile: dict[str, Any], address: int, names: list[str] | None = None
) -> dict[str, Any]:
    opcode = _need(image, address, 1)[0]
    spec = opcode_spec(opcode, profile)
    kind = spec["operand"]
    if kind == "unknown":
        return {
            "address": address,
            "opcode": opcode,
            "bytes": f"{opcode:02x}",
            "size": None,
            "mnemonic": spec["mnemonic"],
            "operandKind": kind,
            "confidence": spec["confidence"],
            "diagnostic": "unknown instruction length; decoding must stop",
        }

    size = _operand_size(kind, image, address, opcode)
    raw = _need(image, address, size)
    result: dict[str, Any] = {
        "address": address,
        "opcode": opcode,
        "bytes": raw.hex(" "),
        "size": size,
        "mnemonic": spec["mnemonic"],
        "operandKind": kind,
        "confidence": spec.get("confidence", "unknown"),
    }
    if "control" in spec:
        result["control"] = spec["control"]
    if "role" in spec:
        result["role"] = spec["role"]
    if "value" in spec:
        result["value"] = spec["value"]
    if "variableIndex" in spec:
        result["variableIndex"] = spec["variableIndex"]
    if kind == "index_u8":
        result["variableIndex"] = raw[1]
    elif kind == "descriptor_u8":
        result["descriptorOffset"] = raw[1]
        descriptor_names = profile.get("layout", {}).get("arrayDescriptors", {})
        result["array"] = descriptor_names.get(f"{raw[1]:02X}", f"ARRAY_DESC_{raw[1]:02X}")
    if "variableIndex" in result and names is not None:
        index = result["variableIndex"]
        result["variable"] = names[index] if index < len(names) else f"VAR_{index:02X}"
    if kind in ("u8", "argc_u8"):
        result["value"] = raw[1]
    elif kind == "u16be":
        result["value"] = raw[1] << 8 | raw[2]
    elif kind == "target_be16":
        result["target"] = raw[1] << 8 | raw[2]
    elif kind == "skip_u8":
        result["skip"] = raw[1]
        result["target"] = (address + raw[1]) & 0xFFFF
    elif kind == "inline_string_u8":
        result["length"] = raw[1]
        result["text"] = _text_bytes(raw[2:])
    elif kind == "inline_string_short":
        result["length"] = opcode & 7
        result["text"] = _text_bytes(raw[1:])
    elif kind == "on_table":
        result["targets"] = [raw[index] << 8 | raw[index + 1] for index in range(2, size, 2)]
    elif kind == "inline_basic_to_colon":
        result["text"] = _text_bytes(raw[1:-1])
        result["terminator"] = raw[-1]
    elif kind == "def_fn_header":
        result["functionDescriptorOffset"] = raw[1] | raw[2] << 8
        result["parameterDescriptorOffset"] = raw[3] | raw[4] << 8
        result["skip"] = raw[5]
        result["bodyTarget"] = address + size
        result["skipTarget"] = (address + raw[5]) & 0xFFFF
    elif kind == "dim5":
        result["dimensions"] = raw[1]
        result["variable"] = decode_var_name(raw[2:4])
        result["flags"] = raw[4]
        result["descriptorOffset"] = raw[5]
    elif kind == "fac5":
        value = decode_fac5(raw[1:])
        result["payload"] = raw[1:].hex(" ")
        result["exactValue"] = (
            str(value.numerator)
            if value.denominator == 1
            else f"{value.numerator}/{value.denominator}"
        )
    elif kind == "fixed5":
        result["payload"] = raw[1:].hex(" ")
    return result


def successors(record: dict[str, Any], profile: dict[str, Any]) -> tuple[list[int], list[str]]:
    if record["size"] is None:
        return [], [record["diagnostic"]]
    fallthrough = record["address"] + record["size"]
    control = record.get("control")
    if control == "goto":
        return [record["target"]], []
    if control == "gosub":
        return [record["target"], fallthrough], []
    if control == "branch":
        return [record["target"], fallthrough], []
    if control in ("multi_branch", "multi_branch_call"):
        return [*record["targets"], fallthrough], []
    if control == "def_fn":
        return [record["skipTarget"], record["bodyTarget"]], []
    if control in ("return", "internal_return"):
        return [], []
    if control == "internal_init":
        target = int(profile["layout"]["initPcode"])
        return [target, fallthrough], ["internal init/return edge is runtime-managed"]
    if control == "next":
        return [fallthrough], ["NEXT target pending conservative lexical inference"]
    return [fallthrough], []


def infer_structured_loop_targets(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conservatively pair lexical FOR_SETUP/NEXT records by descriptor."""
    inferred = []
    stack: list[tuple[int, int, int]] = []  # descriptor, FOR address, body address
    previous = None
    for record in records:
        if (
            previous is not None
            and previous.get("size") is not None
            and previous["address"] + previous["size"] != record["address"]
        ):
            stack.clear()
        contiguous_descriptor = (
            previous is not None
            and (
                previous.get("role") == "variable_descriptor"
                or previous.get("mnemonic") == "VAR_DESCRIPTOR"
                or previous.get("operandKind") == "descriptor_u8"
            )
            and previous.get("size") is not None
            and previous["address"] + previous["size"] == record["address"]
        )
        if record.get("control") == "for_setup" and contiguous_descriptor:
            descriptor = previous.get("descriptorOffset", previous.get("variableIndex"))
            stack.append(
                (descriptor, record["address"], record["address"] + record["size"])
            )
        elif record.get("control") == "next" and contiguous_descriptor:
            descriptor = previous.get("descriptorOffset", previous.get("variableIndex"))
            matches = [index for index, item in enumerate(stack) if item[0] == descriptor]
            if matches:
                index = matches[-1]
                _, setup, body = stack[index]
                del stack[index:]
                record["target"] = body
                record["targetConfidence"] = "strong-structure"
                record["targetEvidence"] = "lexical FOR/NEXT descriptor pairing"
                inferred.append(
                    {"address": record["address"], "setup": setup, "target": body, "descriptorOffset": descriptor}
                )
        if record.get("control") in ("return", "internal_return"):
            stack.clear()
        previous = record
    return inferred


def recursive_decode(
    image: Image, profile: dict[str, Any], entries: list[int], start: int, end: int
) -> dict[str, Any]:
    names = variable_names(image, profile)
    pending = list(dict.fromkeys(entries))
    decoded: dict[int, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    occupied: dict[int, int] = {}
    while pending:
        pc = pending.pop()
        while start <= pc < end and pc not in decoded:
            if pc in occupied:
                diagnostics.append(
                    {"address": pc, "kind": "overlap-entry", "owner": occupied[pc]}
                )
                break
            record = decode_one(image, profile, pc, names)
            decoded[pc] = record
            if record["size"] is None:
                diagnostics.append({"address": pc, "kind": "unknown-length"})
                break
            overlap = False
            for byte_address in range(pc, pc + record["size"]):
                owner = occupied.get(byte_address)
                if owner is not None and owner != pc:
                    diagnostics.append(
                        {"address": pc, "kind": "instruction-overlap", "owner": owner}
                    )
                    overlap = True
                    break
                occupied[byte_address] = pc
            if overlap:
                break
            next_addresses, notes = successors(record, profile)
            diagnostics.extend({"address": pc, "kind": "control-note", "message": note} for note in notes)
            in_range = [value for value in next_addresses if start <= value < end]
            for value in next_addresses:
                if value not in in_range:
                    diagnostics.append(
                        {"address": pc, "kind": "target-outside-range", "target": value}
                    )
            if not in_range:
                break
            pc, *extra = in_range
            pending.extend(extra)
    ordered_records = [decoded[key] for key in sorted(decoded)]
    inferred_loops = infer_structured_loop_targets(ordered_records)
    inferred_addresses = {item["address"] for item in inferred_loops}
    diagnostics = [
        item
        for item in diagnostics
        if not (
            item["address"] in inferred_addresses
            and item.get("message") == "NEXT target pending conservative lexical inference"
        )
    ]
    diagnostics.extend(
        {
            "address": item["address"],
            "kind": "inferred-control",
            "message": f"NEXT target ${item['target']:04X} inferred from lexical FOR/NEXT descriptor pairing",
        }
        for item in inferred_loops
    )
    diagnostics.sort(key=lambda item: (item["address"], item["kind"], item.get("message", "")))
    covered = set(occupied)
    profile_regions = {}
    layout = profile.get("layout", {})
    configured = {
        "init": (layout.get("initPcode"), layout.get("dataStart")),
        "main": (layout.get("mainPcode"), layout.get("pcodeEndExclusive")),
    }
    for name, bounds in configured.items():
        if all(value is not None for value in bounds):
            region_start, region_end = map(int, bounds)
            total = region_end - region_start
            count = sum(address in covered for address in range(region_start, region_end))
            profile_regions[name] = {
                "start": region_start,
                "endExclusive": region_end,
                "bytes": total,
                "decodedBytes": count,
                "undecodedBytes": total - count,
                "coveragePercent": 100.0 * count / total if total else 100.0,
            }
    return {
        "schema": "blitz-pcode-disassembly-v1",
        "image": {
            "path": str(image.path),
            "sha256": image.sha256,
            "loadAddress": image.load,
            "endExclusive": image.end,
        },
        "profile": {"id": profile["id"], "schema": profile["schema"]},
        "range": {"start": start, "endExclusive": end},
        "entries": entries,
        "coverage": {
            "rangeBytes": end - start,
            "decodedBytes": sum(address in covered for address in range(start, end)),
            "profileRegions": profile_regions,
        },
        "instructions": ordered_records,
        "diagnostics": diagnostics,
    }


def render_record(record: dict[str, Any]) -> str:
    address = f"${record['address']:04X}"
    raw = record["bytes"].upper().ljust(24)
    operand = ""
    if record.get("operandKind") == "dim5":
        operand = (
            f"{record['variable']}, dimensions={record['dimensions']}, "
            f"descriptor+${record['descriptorOffset']:02X}"
        )
    elif "variable" in record:
        operand = record["variable"]
    elif "descriptorOffset" in record:
        operand = record.get("array", f"descriptor+${record['descriptorOffset']:02X}")
    elif record.get("operandKind") == "def_fn_header":
        operand = (
            f"function-desc+${record['functionDescriptorOffset']:04X}, "
            f"parameter-desc+${record['parameterDescriptorOffset']:04X}, "
            f"body=${record['bodyTarget']:04X}, skip=${record['skipTarget']:04X}"
        )
    elif "target" in record:
        operand = f"${record['target']:04X}"
    elif "targets" in record:
        operand = ", ".join(f"${target:04X}" for target in record["targets"])
    elif "text" in record:
        operand = json.dumps(record["text"])
    elif "value" in record:
        operand = str(record["value"])
    elif "exactValue" in record:
        operand = f"{record['exactValue']} [{record['payload'].upper()}]"
    elif "payload" in record:
        operand = record["payload"].upper()
    return f"{address}  {raw} {record['mnemonic']:<22} {operand}".rstrip()


def validate_trace(image: Image, profile: dict[str, Any], trace_path: Path) -> dict[str, Any]:
    trace = json.loads(trace_path.read_text())
    names = variable_names(image, profile)
    entries = trace["entries"]
    overrides = {
        int(item["address"]): (int(item["original"]), int(item["observed"]))
        for item in trace.get("memoryPatches", [])
    }
    rows = []
    errors = []
    for index, entry in enumerate(entries):
        address = int(entry["address"])
        record = decode_one(image, profile, address, names)
        logged_opcode = int(entry["opcode"])
        override = overrides.get(address)
        opcode_ok = record["opcode"] == logged_opcode or (
            override is not None
            and record["opcode"] == override[0]
            and logged_opcode == override[1]
        )
        if not opcode_ok:
            errors.append(
                {"index": index, "kind": "opcode-mismatch", "record": record, "logged": logged_opcode}
            )
        next_address = int(entries[index + 1]["address"]) if index + 1 < len(entries) else None
        if next_address is not None and record["size"] is not None:
            allowed, _ = successors(record, profile)
            control = record.get("control")
            if control in ("return", "next", "internal_return", "internal_init"):
                transition_ok = True
            elif next_address in allowed:
                transition_ok = True
            else:
                transition_ok = False
                errors.append(
                    {
                        "index": index,
                        "kind": "unexpected-transition",
                        "from": address,
                        "to": next_address,
                        "allowed": allowed,
                    }
                )
        else:
            transition_ok = record["size"] is not None
        rows.append({"index": index, "nextAddress": next_address, "transitionOk": transition_ok, **record})
    return {
        "schema": "blitz-pcode-trace-validation-v1",
        "trace": str(trace_path),
        "entries": len(entries),
        "errors": errors,
        "records": rows,
    }


def decode_data_block(image: Image, profile: dict[str, Any]) -> dict[str, Any]:
    layout = profile["layout"]
    encoding = layout.get("dataEncoding")
    if encoding != "length-prefixed-strings-ff":
        raise DecodeError(f"unsupported data encoding {encoding!r}")
    start = int(layout["dataStart"])
    end = int(layout["dataEndExclusive"])
    records = []
    address = start
    terminated = False
    while address < end:
        length = image.read(address, 1)[0]
        if length == 0xFF:
            records.append({"address": address, "kind": "terminator", "bytes": "ff", "size": 1})
            address += 1
            terminated = True
            break
        raw = image.read(address + 1, length)
        records.append({
            "address": address,
            "kind": "string",
            "size": length + 1,
            "length": length,
            "bytes": bytes([length]).hex() + " " + raw.hex(" "),
            "text": _text_bytes(raw),
        })
        address += length + 1
    if address != end:
        raise DecodeError(
            f"data block ended at ${address:04X}, configured end is ${end:04X}"
        )
    if not terminated:
        raise DecodeError("data block has no $FF terminator")
    return {
        "schema": "blitz-pcode-data-block-v1",
        "encoding": encoding,
        "start": start,
        "endExclusive": end,
        "records": records,
    }


def profile_info(image: Image, profile: dict[str, Any]) -> dict[str, Any]:
    dispatch = profile.get("dispatch", {})
    handlers = []
    if all(key in dispatch for key in ("directHandlerHighBase", "directHandlerLowBase", "directOpcodeMin", "directOpcodeMax")):
        for opcode in range(int(dispatch["directOpcodeMin"]), int(dispatch["directOpcodeMax"]) + 1):
            high = image.read(int(dispatch["directHandlerHighBase"]) + opcode, 1)[0]
            low = image.read(int(dispatch["directHandlerLowBase"]) + opcode, 1)[0]
            definition = profile.get("exactOpcodes", {}).get(f"{opcode:02X}", {})
            handlers.append({
                "opcode": opcode,
                "handler": high << 8 | low,
                "handlerInPrg": image.contains(high << 8 | low),
                "mnemonic": definition.get("mnemonic"),
                "profiled": bool(definition),
            })
    offsets = []
    if "variableOffsetTable" in dispatch:
        count = int(dispatch.get("variableOffsetCount", 32))
        offsets = list(image.read(int(dispatch["variableOffsetTable"]), count))
    pointers = []
    if "startupPointerTable" in dispatch:
        count = int(dispatch.get("startupPointerCount", 0))
        raw = image.read(int(dispatch["startupPointerTable"]), count * 2)
        pointers = [raw[index] | raw[index + 1] << 8 for index in range(0, len(raw), 2)]
    grouped_handlers = {}
    for item in handlers:
        grouped_handlers.setdefault(item["handler"], []).append(item["opcode"])
    return {
        "image": {"load": image.load, "endExclusive": image.end, "sha256": image.sha256},
        "profile": profile,
        "variables": variable_names(image, profile),
        "directHandlers": handlers,
        "directHandlerGroups": [
            {"handler": handler, "opcodes": opcodes}
            for handler, opcodes in sorted(grouped_handlers.items())
        ],
        "variableDescriptorOffsets": offsets,
        "startupPointers": pointers,
    }


def parse_int(text: str) -> int:
    return int(text, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument(
        "--allow-hash-mismatch",
        action="store_true",
        help="permit a PRG not matching sourcePrgSha256 for deliberate compatibility research",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="report image/profile layout and variable descriptors")
    info.add_argument("prg", type=Path)

    data_cmd = sub.add_parser("data", help="decode the profile-defined extracted DATA block")
    data_cmd.add_argument("prg", type=Path)
    data_cmd.add_argument("--json-output", type=Path)

    one = sub.add_parser("one", help="decode one instruction at an explicit address")
    one.add_argument("prg", type=Path)
    one.add_argument("address", type=parse_int)
    one.add_argument("--json", action="store_true")

    rec = sub.add_parser("recursive", help="conservatively decode reachable p-code")
    rec.add_argument("prg", type=Path)
    rec.add_argument("--entry", type=parse_int, action="append", required=True)
    rec.add_argument("--start", type=parse_int)
    rec.add_argument("--end", type=parse_int)
    rec.add_argument("--json-output", type=Path)
    rec.add_argument("--text-output", type=Path)

    trace = sub.add_parser("validate-trace", help="decode and validate a retained VM-fetch trace")
    trace.add_argument("prg", type=Path)
    trace.add_argument("trace", type=Path)
    trace.add_argument("--json-output", type=Path)

    args = parser.parse_args()
    profile = load_profile(args.profile)
    image = load_prg(args.prg)
    expected = profile.get("sourcePrgSha256")
    if expected and image.sha256 != expected and not args.allow_hash_mismatch:
        raise SystemExit(f"profile expects PRG SHA-256 {expected}, got {image.sha256}")

    if args.command == "info":
        print(json.dumps(profile_info(image, profile), indent=2))
    elif args.command == "data":
        result = decode_data_block(image, profile)
        text = json.dumps(result, indent=2) + "\n"
        if args.json_output:
            args.json_output.write_text(text)
        else:
            print(text, end="")
    elif args.command == "one":
        record = decode_one(image, profile, args.address, variable_names(image, profile))
        print(json.dumps(record, indent=2) if args.json else render_record(record))
    elif args.command == "recursive":
        layout = profile["layout"]
        start = args.start if args.start is not None else int(layout["initPcode"])
        end = args.end if args.end is not None else int(layout["pcodeEndExclusive"])
        result = recursive_decode(image, profile, args.entry, start, end)
        text = json.dumps(result, indent=2) + "\n"
        if args.json_output:
            args.json_output.write_text(text)
        rendered = "\n".join(render_record(record) for record in result["instructions"])
        rendered += "\n; Diagnostics:\n"
        rendered += "\n".join(f"; {diagnostic}" for diagnostic in result["diagnostics"]) + "\n"
        if args.text_output:
            args.text_output.write_text(rendered)
        if not args.json_output and not args.text_output:
            print(rendered, end="")
    else:
        result = validate_trace(image, profile, args.trace)
        text = json.dumps(result, indent=2) + "\n"
        if args.json_output:
            args.json_output.write_text(text)
        print(
            f"trace entries={result['entries']} errors={len(result['errors'])} "
            f"unknown-length={sum(r['size'] is None for r in result['records'])}"
        )
        if result["errors"]:
            print(json.dumps(result["errors"][:20], indent=2))
            raise SystemExit(1)


if __name__ == "__main__":
    main()
