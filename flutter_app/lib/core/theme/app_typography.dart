import 'package:flutter/widgets.dart';
import 'package:google_fonts/google_fonts.dart';

/// Same type scale as frontend/src/theme.tsx's `type` export: Sora for
/// headings (distinct, geometric — the brand voice), IBM Plex Sans for
/// everything read at length. Weight is carried by the font's own weight
/// value here (Flutter doesn't need a separate static file per weight the
/// way the RN app's @expo-google-fonts setup does).
class AppTypography {
  final Color _ink;
  const AppTypography(this._ink);

  TextStyle get display => GoogleFonts.sora(fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -0.6, color: _ink);
  TextStyle get h1 => GoogleFonts.sora(fontSize: 23, fontWeight: FontWeight.w800, letterSpacing: -0.5, color: _ink);
  TextStyle get h2 => GoogleFonts.sora(fontSize: 18, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: _ink);
  TextStyle get body => GoogleFonts.ibmPlexSans(fontSize: 15, fontWeight: FontWeight.w500, color: _ink);
  TextStyle get bodyStrong => GoogleFonts.ibmPlexSans(fontSize: 15, fontWeight: FontWeight.w700, color: _ink);
  TextStyle get small => GoogleFonts.ibmPlexSans(fontSize: 13, fontWeight: FontWeight.w500, color: _ink);
  TextStyle get micro => GoogleFonts.ibmPlexSans(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.6,
        color: _ink,
      );
}
