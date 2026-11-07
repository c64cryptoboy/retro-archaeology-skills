# Source attribution and release caveat

Pinned source evidence makes this record candidate auditable without distributing commercial captures or assuming that all Vorpal layouts are interchangeable.  The Python candidate adapts format tables and logic from Daryl Krans's [ReMaster-Utility](https://github.com/DarylKrans/ReMaster-Utility), commit `f30688de7fede5cef20c0a0d163ec13ec6ef7513`.  ReMaster itself was not executed.

## Applicable source contract

- [V-Max Tool/GCR.cs:84-107](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L84-L107): later Vorpal encoding/decoding tables, including four aliases.
- [V-Max Tool/GCR.cs:246-290](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L246-L290): five-bit symbol extraction and high/low nibble assembly.  Its illegal-symbol-to-zero behavior is explicitly **not** retained.
- [V-Max Tool/Vorpal.cs:179-218](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Vorpal.cs#L179-L218): `7F AA` detector, 1,290 payload/checksum bits, nine ID bits, six selected ID positions, and stated sector range `0..46`.
- [V-Max Tool/Vorpal.cs:249-257](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Vorpal.cs#L249-L257): XOR8 over 128 payload bytes.  The candidate additionally refuses illegal checksum symbols; it does not ignore the source's discarded illegal-symbol count.
- [V-Max Tool/Functions.cs:1093-1114](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Functions.cs#L1093-L1114) and [V-Max Tool/Functions.cs:1345-1352](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Functions.cs#L1345-L1352): MSB-first physical byte extraction and reversal before C# BitArray use.

The early-format tables and differential decoder at [V-Max Tool/GCR.cs:124-143](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L124-L143) and [V-Max Tool/GCR.cs:317-365](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L317-L365) describe a **different** format, excluded from this candidate.  The heuristic fallback at [V-Max Tool/CBM.cs:330-350](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/CBM.cs#L330-L350) is not an admission rule here.  No catch recovery, invalid-byte substitution, checksum repair, or format fallback is ported.

## Pinned file hashes

SHA-256 of the complete, unmodified source files:

| Source path | SHA-256 |
|---|---|
| `V-Max Tool/GCR.cs` | `1809650bebeae7f3caef722824f9a2e5c807d46e1648c77c21808223c90c80cd` |
| `V-Max Tool/Vorpal.cs` | `1695ed2db7b8e8eb21e210e7c82b66afac00d5afb1cfdb788a5d33c0752c3c2a` |
| `V-Max Tool/CBM.cs` | `792096a3e40e06d37e352354f09e7c57a6a8b1848e37ca7211c00bc1a6b854ac` |
| `V-Max Tool/Functions.cs` | `c6c9fc269f2204542e6ffb803f3d6430d113aa10d3adb0bb426746c3764f7ff7` |
| `V-Max Tool/Properties/About.txt` | `cd7fa12b741ab4116678da1ad37967caad19a92524c23bba47f4253456fb1e15` |
| `V-Max Tool/Properties/AssemblyInfo.cs` | `c110c05024202d5bb4d83673f297d02df98f7d466314a8f4f2d88fe895c75fcd` |
| `README.md` | `1b57a386ae7df4236f52d927be781ed3797c5ed60cf4eadc974651fa7a6cfb23` |

## Licensing and credits

The pinned [`V-Max Tool/Properties/About.txt`](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Properties/About.txt) states “Programmed by Daryl Krans (2023–2025)” and “No rights reserved.”  It credits **Luigi Di Fraia for Vorpal GCR encoding documentation** and **Pete Rittwage, author of Nibtools**, among other contributors.  Preserve these credits.

As recorded by the existing RapidLok source audit, no tracked LICENSE, COPYING, or NOTICE file was found at this revision.  [`V-Max Tool/Properties/AssemblyInfo.cs:12`](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Properties/AssemblyInfo.cs#L12) retains `Copyright ©  2023`.  The About statement is meaningful permission evidence, but its scope and third-party coverage remain uncertain; no specific license or universal waiver is inferred.  The [README](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/README.md) also warns that development source may be buggy or incomplete.

The helper and synthetic tests require no commercial captures or copied reference checkout.  Source attribution and licensing uncertainty must accompany copies or adaptations.  See the [repository notices](../../../../THIRD_PARTY_NOTICES.md).
