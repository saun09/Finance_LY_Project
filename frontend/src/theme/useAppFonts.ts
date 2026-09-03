import {
  Fraunces_500Medium_Italic,
  Fraunces_600SemiBold,
  useFonts as useFraunces,
} from '@expo-google-fonts/fraunces';
import {
  IBMPlexSans_400Regular,
  IBMPlexSans_500Medium,
  IBMPlexSans_600SemiBold,
  useFonts as usePlexSans,
} from '@expo-google-fonts/ibm-plex-sans';
import { IBMPlexMono_500Medium, IBMPlexMono_600SemiBold, useFonts as usePlexMono } from '@expo-google-fonts/ibm-plex-mono';

export function useAppFonts() {
  const [frauncesLoaded] = useFraunces({ Fraunces_600SemiBold, Fraunces_500Medium_Italic });
  const [plexSansLoaded] = usePlexSans({ IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold });
  const [plexMonoLoaded] = usePlexMono({ IBMPlexMono_500Medium, IBMPlexMono_600SemiBold });
  return frauncesLoaded && plexSansLoaded && plexMonoLoaded;
}
