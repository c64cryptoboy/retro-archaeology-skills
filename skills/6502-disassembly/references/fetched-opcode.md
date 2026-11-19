# Which opcode did the CPU fetch?

A coverage mark can tell you where to look for mutable code, but not which version to put in the executed disassembly.  Suppose the only question is whether the CPU fetched a temporary `DEX` at `$6200`.  Keep the CPU, physical RAM mapping, and initial byte fixed.  The following are two **alternative recordings**, not consecutive parts of one run:

| Recording | Initial byte | Events at `$6200`, in order | Final byte |
|---|---|---|---|
| A | `$E8` (`INX`) | write `$CA`; fetch `$CA` (`DEX`); restore `$E8` | `$E8` |
| B | `$E8` (`INX`) | write `$CA`; restore `$E8`; fetch `$E8` (`INX`) | `$E8` |

Both recordings have the same endpoint bytes, the same ordered list of writes, one opcode fetch, and a write before that fetch.  Only A fetched `DEX`.  Even an exact comparison of the endpoint byte misses the distinction; it is the position of the fetch **relative to the restore** that matters.

**Report the strongest claim the observation supports:**

1. If writes and executes come from separate coverage maps, test for both **within each recording and mapping before combining results**.  A write in one playthrough and a fetch in another establish neither event pair in one playthrough.
2. If one recording marks both at the same RAM address, report “written and executed in this recording; fetched version unknown.”  Keep the map and recording ID.  Do not choose either opcode from the endpoint dump for that visit.
3. To resolve that visit, retain the ordered write and opcode-fetch records with their values and mapping.  Alternatively, infer the fetched byte from the last preceding write only if the initial state, all intervening writes, mapping, and fetch position are known.  Distinguish that reconstruction from a directly observed fetch value.  A sampled PC or later debugger disassembly supplies no fetch value by itself.  A hit limit or trace gap is not evidence that no restore occurred.

For a code-reuse comparison, a captured `DEX` byte may still be compared as captured bytes.  Describe it as an **executed** variant only if the witness supports that claim.  This example is about one opcode byte; an instruction with operands needs separate evidence for the operand bytes consumed.

**Reproduce:** From the skill directory, run `python3 -B scripts/check_fetch_witness.py`.  The motivating [c64-re-tools coverage test](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/knowledge/program.test.ts#L151-L172) distinguishes same-recording write/execute marks from marks combined across recordings.  It checks the cross-recording false positive, the two indistinguishable summaries above, and rejection of a fetch value inconsistent with the complete synthetic log.  It needs no emulator, historical binary, or third-party package.
