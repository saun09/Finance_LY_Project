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

type Nav = NativeStackNavigationProp<AuthStackParamList, 'Login'>;

export function LoginScreen() {
  const navigation = useNavigation<Nav>();
  const { login } = useDemoUser();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const loginMutation = useMutation({
    mutationFn: async () => {
      if (!username.trim() || !password) throw new Error('validation');
      await login(username, password);
    },
    onError: (err) => {
      setError(
        err instanceof Error && err.message === 'validation'
          ? 'Enter your username and password.'
          : (err as Error).message,
      );
    },
  });

  return (
    <ScreenContainer scroll={false} contentStyle={styles.container}>
      <View style={styles.top}>
        <Text variant="label" tone="terracotta">
          WELCOME BACK
        </Text>
        <Text variant="display" style={styles.headline}>
          Log in
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
          placeholder="••••••••"
        />
        {error ? <InlineError message={error} /> : null}
        <Button
          label="Log in"
          fullWidth
          loading={loginMutation.isPending}
          onPress={() => {
            setError(null);
            loginMutation.mutate();
          }}
        />
      </Card>

      <View style={styles.bottom}>
        <Button label="Create a new account" variant="ghost" fullWidth onPress={() => navigation.navigate('Signup')} />
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
