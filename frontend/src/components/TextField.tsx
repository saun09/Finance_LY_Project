import React from 'react';
import { KeyboardTypeOptions, StyleSheet, TextInput, View } from 'react-native';
import { FONT, RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  keyboardType?: KeyboardTypeOptions;
  error?: string | null;
  helperText?: string;
  prefix?: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  multiline?: boolean;
}

/** The one text-input primitive every onboarding form uses -- labeled,
 * with an optional inline prefix (e.g. "₹" for a rupee amount field) and
 * an error slot styled from the shared danger token, never an ad hoc red. */
export function TextField({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType = 'default',
  error,
  helperText,
  prefix,
  autoCapitalize = 'sentences',
  multiline = false,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      <Text variant="label" tone="muted">
        {label.toUpperCase()}
      </Text>
      <View
        style={[
          styles.inputRow,
          multiline && styles.inputRowMultiline,
          { backgroundColor: colors.paper, borderColor: error ? colors.danger : colors.border },
        ]}
      >
        {prefix ? (
          <Text variant="figure" tone="muted" style={styles.prefix}>
            {prefix}
          </Text>
        ) : null}
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.inkFaint}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          multiline={multiline}
          textAlignVertical={multiline ? 'top' : 'center'}
          style={[
            styles.input,
            multiline && styles.inputMultiline,
            { color: colors.ink, fontFamily: prefix ? FONT.mono : FONT.body },
          ]}
        />
      </View>
      {error ? (
        <Text variant="caption" tone="danger">
          {error}
        </Text>
      ) : helperText ? (
        <Text variant="caption" tone="faint">
          {helperText}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: SPACE.xs },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderRadius: RADIUS.md,
    paddingHorizontal: SPACE.md,
    minHeight: 50,
  },
  inputRowMultiline: { alignItems: 'flex-start', paddingVertical: SPACE.sm },
  prefix: { marginRight: SPACE.xs },
  input: { flex: 1, fontSize: 15, paddingVertical: SPACE.sm },
  inputMultiline: { minHeight: 96, paddingVertical: 0 },
});
