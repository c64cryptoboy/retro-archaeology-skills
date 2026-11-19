\version "2.24.0"
#(set-global-staff-size 16)
\header {
  title = "Two-bar gate study"
  subtitle = "Reading grid  |  Authored example"
  subsubtitle = "* = moving pitch bend"
  tagline = ##f
}
\paper { indent = 15\mm short-indent = 9\mm }
\score {
  <<
    \new Staff \with {
      instrumentName = "Reed"
      shortInstrumentName = "R"
    } {
      \omit Staff.TimeSignature
      \clef "treble"
      \tempo \markup { "Editorial quarter = 100.00 BPM" }
      \set Score.tempoWholesPerMinute = #(ly:make-moment 25 1)
      \set Timing.measureLength = #(ly:make-moment 32 32)
      c'4 c'4 r4 g'4^\markup \tiny "*"~ | % 1
      g'4 r8 a'8~ a'8 r8 r4 | % 2
      \bar "|."
    }
    \new Staff \with {
      instrumentName = "Low"
      shortInstrumentName = "L"
    } {
      \omit Staff.TimeSignature
      \clef "bass"
      \set Timing.measureLength = #(ly:make-moment 32 32)
      r8 c8~ c4. r8 r4 | % 1
      r8 f8~ f4 r2 | % 2
      \bar "|."
    }
  >>
  \layout { }
  \midi { }
}
