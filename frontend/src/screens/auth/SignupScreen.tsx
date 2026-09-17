import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import type { AuthStackParamList } from '../../navigation/types';
import { SPACE } from '../../theme/tokens';

type Nav = NativeStackNavigationProp<AuthStackParamList, 'Signup'>;

const MIN_PASSWORD_LENGTH = 8;

export function SignupScreen() {
  const navigation = useNavigation<Nav>();
  const { signup } = useDemoUser();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const signupMutation = useMutation({
    mutationFn: async () => {
      if (!username.trim() || !password) throw new Error('validation:Enter a username and password.');
      if (password.length < MIN_PASSWORD_LENGTH) {
        throw new Error(`validation:Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      }
      if (password !== confirmPassword) throw new Error('validation:Passwords do not match.');
      await signup(username, password);
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Something went wrong.';
      setError(message.startsWith('validation:') ? message.slice('validation:'.length) : message);
    },
  });

  return (
    <ScreenContainer scroll={false} contentStyle={styles.container}>
      <View style={styles.top}>
        <Text variant="label" tone="terracotta">
          NEW HERE?
        </Text>
        <Text variant="display" style={styles.headline}>
          Create an account
        </Text>
      </View>

      <Card style={styles.formCard}>
        <TextField
          label="Username"
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          placeholder="yourname"
        />
        <TextField
          label="Password"
          value={password}
          onChangeText={setPassword}
          autoCapitalize="none"
          secureTextEntry
          placeholder="At least 8 characters"
        />
        <TextField
          label="Confirm password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          autoCapitalize="none"
          secureTextEntry
          placeholder="••••••••"
        />
        {error ? <InlineError message={error} /> : null}
        <Button
          label="Create account"
          fullWidth
          loading={signupMutation.isPending}
          onPress={() => {
            setError(null);
            signupMutation.mutate();
          }}
        />
      </Card>

      <View style={styles.bottom}>
        <Button label="I already have an account" variant="ghost" fullWidth onPress={() => navigation.navigate('Login')} />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { justifyContent: 'space-between' },
  top: { gap: SPACE.md, marginTop: SPACE.xxl },
  headline: { marginTop: SPACE.sm },
  formCard: { gap: SPACE.md },
  bottom: { gap: SPACE.sm },
});
