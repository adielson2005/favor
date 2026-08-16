// Loads the FAZÊ type family: Manrope for headings, IBM Plex Sans for body/UI text.
// Mirrors use-icon-fonts.ts's pattern — same useFonts call, held behind the splash screen in _layout.tsx.
import { IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold, IBMPlexSans_700Bold } from "@expo-google-fonts/ibm-plex-sans";
import { Manrope_700Bold, Manrope_800ExtraBold } from "@expo-google-fonts/manrope";
import { useFonts } from "expo-font";

export const fonts = {
  headingBold: "Manrope_700Bold",
  headingExtraBold: "Manrope_800ExtraBold",
  body: "IBMPlexSans_400Regular",
  bodyMedium: "IBMPlexSans_500Medium",
  bodySemiBold: "IBMPlexSans_600SemiBold",
  bodyBold: "IBMPlexSans_700Bold",
};

export const useAppFonts = (): readonly [boolean, Error | null] =>
  useFonts({
    Manrope_700Bold,
    Manrope_800ExtraBold,
    IBMPlexSans_400Regular,
    IBMPlexSans_500Medium,
    IBMPlexSans_600SemiBold,
    IBMPlexSans_700Bold,
  });
