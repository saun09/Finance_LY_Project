import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import type { HoldingOut, HoldingType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { FloatingActionButton } from '../../components/FloatingActionButton';
import { FormSheet } from '../../components/FormSheet';
import { HoldingTypePicker, HOLDING_TYPE_LABEL } from '../../components/HoldingTypePicker';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useHoldings } from '../../hooks/useProfileManagement';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

export function HoldingsManageScreen() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useHoldings();

  const [sheetOpen, setSheetOpen] = useState(false);
  const [description, setDescription] = useState('');
  const [valueInput, setValueInput] = useState('');
  const [holdingType, setHoldingType] = useState<HoldingType | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const value_paise = rupeeInputToPaise(valueInput);
      if (!description.trim() || value_paise === null) throw new Error('validation');
      return onboardingApi.postHolding(userId, { description: description.trim(), value_paise, holding_type: holdingType });
    },
    onSuccess: () => {
      setDescription('');
      setValueInput('');
      setHoldingType(null);
      setSheetOpen(false);
      queryClient.invalidateQueries({ queryKey: qk.holdings(userId) });
      invalidateFinancialData(queryClient, userId);
    },
    onError: (err) =>
      setFormError(err instanceof Error && err.message === 'validation' ? 'Enter a description and a value.' : toApiError(err).message),
  });

  // Classify an existing holding. A holding saved as "not sure" blocks the
  // Allocation screen until it has a type, so this is how a user unblocks it.
  const [editing, setEditing] = useState<HoldingOut | null>(null);
  const [editType, setEditType] = useState<HoldingType | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const openEdit = (item: HoldingOut) => {
    setEditing(item);
    setEditType(item.holding_type);
    setEditError(null);
  };
  const typeMutation = useMutation({
    mutationFn: async () => {
      if (!editing || !editType) throw new Error('validation');
      return onboardingApi.setHoldingType(userId, editing.id, editType);
    },
    onSuccess: () => {
      setEditing(null);
      queryClient.invalidateQueries({ queryKey: qk.holdings(userId) });
      invalidateFinancialData(queryClient, userId);
    },
    onError: (err) =>
      setEditError(err instanceof Error && err.message === 'validation' ? 'Pick a type for this holding.' : toApiError(err).message),
  });
  const unclassifiedCount = data?.filter((h) => !h.holding_type).length ?? 0;

  return (
    <ScreenContainer floatingAction={<FloatingActionButton label="Add holding" onPress={() => setSheetOpen(true)} />}>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Holdings</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <Card>
          <EmptyState title="No holdings yet" message="Tap “Add holding” below to record your savings and investments." />
        </Card>
      ) : (
        <Card>
          {unclassifiedCount > 0 ? (
            <Text variant="caption" tone="warning">
              {unclassifiedCount === 1 ? '1 holding needs' : `${unclassifiedCount} holdings need`} a type before your
              target allocation can be worked out. Tap it to set one.
            </Text>
          ) : null}
          {data.map((item) => (
            <ListRow
              key={item.id}
              title={item.description}
              subtitle={item.holding_type ? HOLDING_TYPE_LABEL[item.holding_type] : 'Type not specified — tap to set'}
              trailing={formatPaise(item.value_paise)}
              onPress={() => openEdit(item)}
            />
          ))}
        </Card>
      )}

      <FormSheet visible={sheetOpen} onClose={() => setSheetOpen(false)} title="Add a holding">
        <TextField label="Description" value={description} onChangeText={setDescription} placeholder="HDFC Flexicap SIP" />
        <TextField
          label="Current value"
          value={valueInput}
          onChangeText={setValueInput}
          placeholder="2,50,000"
          keyboardType="numeric"
          prefix="₹"
          formatAsCurrency
        />
        <HoldingTypePicker value={holdingType} onChange={setHoldingType} />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add holding"
          fullWidth
          loading={addMutation.isPending}
          onPress={() => {
            setFormError(null);
            addMutation.mutate();
          }}
        />
      </FormSheet>

      <FormSheet visible={!!editing} onClose={() => setEditing(null)} title={editing ? editing.description : 'Holding type'}>
        <HoldingTypePicker value={editType} onChange={setEditType} />
        {editError ? <InlineError message={editError} /> : null}
        <Button
          label="Save type"
          fullWidth
          disabled={!editType}
          loading={typeMutation.isPending}
          onPress={() => {
            setEditError(null);
            typeMutation.mutate();
          }}
        />
      </FormSheet>
    </ScreenContainer>
  );
}
