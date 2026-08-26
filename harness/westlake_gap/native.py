"""Native-library provenance and static JNI registration-table recovery."""

from __future__ import annotations

import io
import re
import struct
from pathlib import PurePosixPath
from typing import Any

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection


MACHINE_ABIS = {
    "AArch64": "arm64-v8a",
    "ARM": "armeabi-v7a",
    "Intel 80386": "x86",
    "Advanced Micro Devices X86-64": "x86_64",
    "RISC-V": "riscv64",
}
ABI_MACHINES = {value: key for key, value in MACHINE_ABIS.items()}
METHOD_NAME_RE = re.compile(r"^[^\s/;().\[\]]{1,512}$")
METHOD_DESCRIPTOR_RE = re.compile(
    r"^\((?:\[*(?:[ZBCSIJFD]|L[^;]{1,1024};))*\)\[*(?:[VZBCSIJFD]|L[^;]{1,1024};)$"
)


def abi_from_machine(machine: str | None) -> str | None:
    return MACHINE_ABIS.get(machine or "")


def abi_from_archive_name(name: str) -> str | None:
    """Return the Android ABI encoded in ``...!lib/<abi>/name.so``."""
    inner = name.rsplit("!", 1)[-1]
    parts = PurePosixPath(inner).parts
    if len(parts) >= 3 and parts[0] == "lib":
        return parts[1]
    return None


def library_filename(value: str) -> str:
    """Normalize System.loadLibrary/load strings to a packaged ELF filename."""
    name = PurePosixPath(value).name
    if not name.endswith(".so"):
        name = f"lib{name}.so"
    return name


def recover_jni_registration_entries(data: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Recover likely JNINativeMethod triples from linked ELF data.

    A JNINativeMethod array contains three pointers: method name, descriptor, and native
    function. Shared objects usually relocate the first two pointers into read-only strings and
    the third into an executable segment. This parser resolves ordinary REL/RELA relocations and
    scans allocated data sections. Android packed/dynamic tables that are constructed at runtime
    intentionally remain unresolved.
    """
    try:
        elf = ELFFile(io.BytesIO(data))
        pointer_size = 8 if elf.elfclass == 64 else 4
        byte_order = "<" if elf.little_endian else ">"
        pointer_format = byte_order + ("Q" if pointer_size == 8 else "I")
        relocated = _relocated_values(elf, data, pointer_size, pointer_format)
        load_segments = [segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"]

        def read_pointer(address: int) -> int | None:
            if address in relocated:
                return relocated[address]
            offset = _vaddr_to_offset(load_segments, address, pointer_size)
            if offset is None:
                return None
            return int(struct.unpack_from(pointer_format, data, offset)[0])

        def read_string(address: int) -> str | None:
            offset = _vaddr_to_offset(load_segments, address, 1)
            if offset is None:
                return None
            end = data.find(b"\0", offset, min(len(data), offset + 2049))
            if end < 0:
                return None
            try:
                return data[offset:end].decode("utf-8")
            except UnicodeDecodeError:
                return None

        def executable(address: int) -> bool:
            address &= ~1  # ARM Thumb function pointers carry bit zero as state.
            return any(
                int(segment["p_vaddr"]) <= address < int(segment["p_vaddr"] + segment["p_memsz"])
                and int(segment["p_flags"]) & 1
                for segment in load_segments
            )

        entries: dict[tuple[str, str, int], dict[str, Any]] = {}
        for section in elf.iter_sections():
            flags = int(section["sh_flags"])
            if not flags & 0x2 or flags & 0x4:  # SHF_ALLOC, not SHF_EXECINSTR.
                continue
            size = int(section["sh_size"])
            if size < pointer_size * 3 or section["sh_type"] == "SHT_NOBITS":
                continue
            start = int(section["sh_addr"])
            for relative in range(0, size - pointer_size * 3 + 1, pointer_size):
                table_address = start + relative
                name_pointer = read_pointer(table_address)
                signature_pointer = read_pointer(table_address + pointer_size)
                function_pointer = read_pointer(table_address + pointer_size * 2)
                if not name_pointer or not signature_pointer or not function_pointer:
                    continue
                name = read_string(name_pointer)
                signature = read_string(signature_pointer)
                if not name or not signature:
                    continue
                if not METHOD_NAME_RE.fullmatch(name) or not METHOD_DESCRIPTOR_RE.fullmatch(signature):
                    continue
                if not executable(function_pointer):
                    continue
                key = (name, signature, function_pointer)
                entries[key] = {
                    "name": name,
                    "signature": signature,
                    "function_vaddr": function_pointer,
                    "table_vaddr": table_address,
                    "section": section.name,
                }
        return sorted(entries.values(), key=lambda item: (item["name"], item["signature"], item["function_vaddr"])), None
    except Exception as exc:  # Corrupt and deliberately unusual APK ELFs are expected inputs.
        return [], f"{type(exc).__name__}: {exc}"


def _relocated_values(
    elf: ELFFile,
    data: bytes,
    pointer_size: int,
    pointer_format: str,
) -> dict[int, int]:
    values: dict[int, int] = {}
    load_segments = [segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"]
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection):
            continue
        symbol_table = elf.get_section(section["sh_link"]) if int(section["sh_link"]) else None
        for relocation in section.iter_relocations():
            target = int(relocation["r_offset"])
            symbol_value = 0
            symbol_index = int(relocation["r_info_sym"])
            if symbol_index and symbol_table is not None:
                symbol_value = int(symbol_table.get_symbol(symbol_index)["st_value"])
            if relocation.is_RELA():
                addend = int(relocation["r_addend"])
            else:
                offset = _vaddr_to_offset(load_segments, target, pointer_size)
                if offset is None:
                    continue
                addend = int(struct.unpack_from(pointer_format, data, offset)[0])
            values[target] = symbol_value + addend
    return values


def _vaddr_to_offset(segments: list[Any], address: int, size: int) -> int | None:
    for segment in segments:
        start = int(segment["p_vaddr"])
        file_size = int(segment["p_filesz"])
        if start <= address and address + size <= start + file_size:
            return int(segment["p_offset"]) + address - start
    return None
