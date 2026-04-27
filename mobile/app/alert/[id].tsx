import { useEffect, useState } from "react";
import { ActivityIndicator, Button, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Video, ResizeMode } from "expo-av";
import { Alert, clipUrl, listAlerts, postFeedback } from "../../src/api";

export default function AlertDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listAlerts()
      .then((arr) => setAlert(arr.find((a) => a.id === id) ?? null))
      .catch(console.warn);
  }, [id]);

  async function feedback(isFalsePositive: boolean) {
    if (!alert) return;
    setBusy(true);
    try {
      await postFeedback(alert.id, isFalsePositive);
      router.back();
    } catch (e) {
      console.warn(e);
    } finally {
      setBusy(false);
    }
  }

  if (!alert) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Video
        source={{ uri: clipUrl(alert.s3_key) }}
        style={styles.video}
        useNativeControls
        resizeMode={ResizeMode.CONTAIN}
      />
      <View style={styles.body}>
        <Text style={styles.title}>{alert.rule_name || alert.preset_type}</Text>
        <Text style={styles.meta}>
          score {alert.score.toFixed(2)} · {new Date(alert.created_at).toLocaleString("pt-BR")}
        </Text>
        <Text style={styles.msg}>{alert.message}</Text>
        {alert.status === "pending" && (
          <View style={styles.actions}>
            <Button title="Confirmar" disabled={busy} onPress={() => feedback(false)} />
            <Button title="Falso positivo" disabled={busy} color="#d33" onPress={() => feedback(true)} />
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  video: { width: "100%", aspectRatio: 4 / 3, backgroundColor: "#000" },
  body: { padding: 16 },
  title: { fontSize: 18, fontWeight: "600" },
  meta: { color: "#888", marginTop: 4 },
  msg: { fontSize: 15, marginTop: 12, lineHeight: 22 },
  actions: { flexDirection: "row", gap: 12, marginTop: 24, justifyContent: "space-between" },
});
