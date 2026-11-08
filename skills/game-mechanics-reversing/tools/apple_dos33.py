#!/usr/bin/env python3
"""Read active files from 35-track DOS 3.3 logical-sector (.do) images.

The pure read_image API returns a JSON-compatible manifest and byte artifacts.
Unsupported image geometry raises ValueError.  Damaged supported structures are
reported in manifest['issues']; observed catalog, T/S-list, and data sectors are
retained.  A broken allocation chain, duplicate logical slot, or gap suppresses
assembled file artifacts, rather than inventing missing bytes.  'Contiguous'
describes observed allocation, not a certification that a file is undamaged.

Files use catalog-chain ordinal * 7 + catalog slot as their entry ID, including
unused/deleted slots in that numbering.  Disk names are metadata only.  Each
file's data_sectors maps evidence artifacts to logical file-sector positions.
For A/I/B files with an in-bounds length header, allocated.bin is split into
header.bin, payload.bin, and slack.bin.  Other types retain allocation only;
text has no reliable length header.  No BASIC decoding, text reconstruction,
deleted-file recovery, ProDOS, physical-sector reordering, or flux support.

Format facts: Apple II DOS and ProDOS Mini-Manual, questions 20 and 21:
https://mirrors.apple2.org.za/apple.cabi.net/FAQs.and.INFO/A2.CSA2.FAQS.IN.HTML/apple.II.dos.and.prodos.mi.html
The saved format excerpts and an earlier task-local extractor were consulted.
This reader contains no third-party token table, decoder, or source excerpt.
"""

TRACKS = 35
SECTORS = 16
SECTOR_BYTES = 256
IMAGE_BYTES = TRACKS * SECTORS * SECTOR_BYTES
TS_PAIRS = 122
TYPES = {0: 'T', 1: 'I', 2: 'A', 4: 'B', 8: 'S', 16: 'R', 32: 'a', 64: 'b'}


def read_image(data: bytes) -> tuple[dict, dict[str, bytes]]:
    """Return observed DOS 3.3 metadata and artifacts without filesystem writes."""
    if len(data) != IMAGE_BYTES:
        raise ValueError(f'expected {IMAGE_BYTES} bytes for a 35-track DOS 3.3 .do image')

    def valid(track, sector):
        return 0 <= track < TRACKS and 0 <= sector < SECTORS

    def sector_bytes(track, sector):
        if not valid(track, sector):
            raise ValueError(f'invalid sector coordinate {track}/{sector}')
        offset = (track * SECTORS + sector) * SECTOR_BYTES
        return data[offset:offset + SECTOR_BYTES]

    vtoc = sector_bytes(17, 0)
    if vtoc[3] != 3 or vtoc[0x34:0x38] != bytes([35, 16, 0, 1]):
        raise ValueError('unsupported VTOC: require DOS 3.3, 35 tracks, 16 sectors, and 256-byte sectors')
    if vtoc[0x27] != TS_PAIRS:
        raise ValueError('unsupported VTOC: require 122 T/S pairs per list')

    artifacts = {'metadata/vtoc.bin': vtoc}
    issues = []
    owners = {}

    def issue(code, message, entry_id=None):
        diagnostic = {'code': code, 'message': message}
        if entry_id is not None:
            diagnostic['entry_id'] = entry_id
        issues.append(diagnostic)

    def retain(track, sector, path, owner):
        raw = sector_bytes(track, sector)
        artifacts[path] = raw
        coordinate = (track, sector)
        if coordinate in owners:
            issue('sector_overlap', f'sector {track}/{sector}: {owners[coordinate]} and {owner}')
        else:
            owners[coordinate] = owner
        # Bitmap bytes 0 and 1 hold sectors 15 through 0, most significant first.
        bitmap = int.from_bytes(vtoc[0x38 + track * 4:0x3A + track * 4], 'big')
        if bitmap & (1 << sector):
            issue('referenced_sector_free', f'sector {track}/{sector} marked free: {owner}')
        return {'track': track, 'sector': sector,
                'image_offset': (track * SECTORS + sector) * SECTOR_BYTES,
                'artifact': path}

    vtoc_location = retain(17, 0, 'metadata/vtoc.bin', 'VTOC')
    catalogs = []
    entries = []
    track, sector = vtoc[1:3]
    visited = set()
    catalog_complete = True
    while track:
        if not valid(track, sector):
            issue('invalid_catalog_coordinate', f'invalid catalog sector {track}/{sector}')
            catalog_complete = False
            break
        if (track, sector) in visited:
            issue('catalog_cycle', f'catalog revisits {track}/{sector}')
            catalog_complete = False
            break
        visited.add((track, sector))
        catalog_index = len(catalogs)
        location = retain(track, sector, f'metadata/catalog-{catalog_index:03d}.bin', 'catalog')
        raw = sector_bytes(track, sector)
        catalogs.append(dict(location, next=list(raw[1:3])))
        for slot in range(7):
            offset = 11 + slot * 35
            record = raw[offset:offset + 35]
            if record[0] in (0, 255):
                continue
            entry_number = catalog_index * 7 + slot
            entries.append({
                'id': f'entry-{entry_number:03d}',
                'name': bytes(value & 127 for value in record[3:33]).decode('ascii').rstrip(' '),
                'name_raw_hex': record[3:33].hex(),
                'catalog': dict(location, chain_index=catalog_index, slot=slot,
                                entry_offset=offset, entry_hex=record.hex()),
                'ts_start': list(record[:2]),
                'type_byte': record[2], 'type': TYPES.get(record[2] & 127, 'unknown'),
                'locked': bool(record[2] & 128),
                'catalog_sectors': int.from_bytes(record[33:35], 'little'),
            })
        track, sector = raw[1:3]
    if not track and sector:
        issue('nonzero_catalog_terminator', f'catalog ends with track 0 and sector {sector}')
        catalog_complete = False

    for entry in entries:
        entry_id = entry['id']
        prefix = f'files/{entry_id}'
        track, sector = entry['ts_start']
        visited = set()
        lists = []
        observed = []
        slots = {}
        allocation_complete = True
        while track:
            if not valid(track, sector):
                issue('invalid_ts_coordinate', f'invalid T/S-list sector {track}/{sector}', entry_id)
                allocation_complete = False
                break
            if (track, sector) in visited:
                issue('ts_cycle', f'T/S list revisits {track}/{sector}', entry_id)
                allocation_complete = False
                break
            visited.add((track, sector))
            location = retain(track, sector, f'{prefix}/ts-list-{len(lists):03d}.bin', entry_id + ' T/S')
            raw = sector_bytes(track, sector)
            start = int.from_bytes(raw[5:7], 'little')
            lists.append(dict(location, file_sector_start=start, next=list(raw[1:3])))
            for pair in range(TS_PAIRS):
                pair_offset = 12 + pair * 2
                data_track, data_sector = raw[pair_offset:pair_offset + 2]
                if data_track == data_sector == 0:
                    continue
                index = start + pair
                if not valid(data_track, data_sector):
                    issue('invalid_data_coordinate',
                          f'file sector {index} points to {data_track}/{data_sector}', entry_id)
                    allocation_complete = False
                    continue
                path = f'{prefix}/data-{len(observed):04d}.bin'
                location = retain(data_track, data_sector, path, entry_id + ' data')
                observed.append(dict(location, file_sector=index,
                                     ts_list=[track, sector], pair_offset=pair_offset))
                if index in slots:
                    issue('duplicate_file_sector', f'duplicate logical file sector {index}', entry_id)
                    allocation_complete = False
                else:
                    slots[index] = artifacts[path]
            track, sector = raw[1:3]
        if not track and sector:
            issue('nonzero_ts_terminator', f'T/S chain ends with track 0 and sector {sector}', entry_id)
            allocation_complete = False

        maximum = max(slots, default=-1)
        gaps = [index for index in range(maximum + 1) if index not in slots]
        count = len(lists) + len(observed)
        entry.update(ts_lists=lists, data_sectors=observed, gaps=gaps,
                     allocation_chain_complete=allocation_complete,
                     observed_sector_references=count, assembly='not_assembled',
                     payload_status='not_assembled')
        if count != entry['catalog_sectors']:
            issue('catalog_allocation_mismatch',
                  f'catalog says {entry["catalog_sectors"]} sectors; observed {count} references', entry_id)
        if gaps:
            issue('file_gaps', f'{len(gaps)} missing logical sectors before sector {maximum}', entry_id)
        if gaps or not allocation_complete:
            continue

        allocated = b''.join(slots[index] for index in range(maximum + 1))
        artifacts[f'{prefix}/allocated.bin'] = allocated
        entry.update(assembly='contiguous', allocated_data_bytes=len(allocated))
        file_type = entry['type']
        if file_type not in ('A', 'I', 'B'):
            entry['payload_status'] = 'no_length_header' if file_type == 'T' else 'unsupported_type'
            if file_type == 'T':
                first_nul = allocated.find(b'\0')
                entry['first_nul'] = first_nul if first_nul >= 0 else None
                entry['nonzero_after_first_nul'] = first_nul >= 0 and any(allocated[first_nul + 1:])
            else:
                issue('unsupported_payload_type', f'no payload interpretation for type {file_type}', entry_id)
            continue

        header_size = 4 if file_type == 'B' else 2
        entry['header_bytes'] = header_size
        if len(allocated) < header_size:
            issue('short_header', f'need {header_size} header bytes, have {len(allocated)}', entry_id)
            entry['payload_status'] = 'invalid_header'
            continue
        length_offset = 2 if file_type == 'B' else 0
        length = int.from_bytes(allocated[length_offset:length_offset + 2], 'little')
        entry['declared_payload_bytes'] = length
        if file_type == 'B':
            entry['binary_load_address'] = int.from_bytes(allocated[:2], 'little')
        artifacts[f'{prefix}/header.bin'] = allocated[:header_size]
        if header_size + length > len(allocated):
            issue('payload_exceeds_allocation',
                  f'header requests {length} payload bytes; only {len(allocated) - header_size} available', entry_id)
            entry['payload_status'] = 'invalid_header'
            continue
        end = header_size + length
        artifacts[f'{prefix}/payload.bin'] = allocated[header_size:end]
        artifacts[f'{prefix}/slack.bin'] = allocated[end:]
        entry.update(payload_status='bounded_by_header', payload_bytes=length,
                     slack_bytes=len(allocated) - end)

    manifest = {
        'format': 'apple-dos33-do',
        'geometry': {'tracks': TRACKS, 'sectors_per_track': SECTORS, 'sector_bytes': SECTOR_BYTES},
        'volume': vtoc[6], 'vtoc': vtoc_location,
        'catalog_chain': catalogs, 'catalog_chain_complete': catalog_complete,
        'files': entries, 'issues': issues,
        'scope': 'active files only; raw DOS 3.3 .do; no decoding or random-access text reconstruction',
    }
    return manifest, artifacts


if __name__ == '__main__':
    from disk_image_output import run_cli

    raise SystemExit(run_cli(read_image, description='Extract raw active files from a 35-track DOS 3.3 .do image.'))
