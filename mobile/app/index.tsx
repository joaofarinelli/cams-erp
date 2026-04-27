import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Link, Stack } from "expo-router";
import { Alert, listAlerts, openAlertStream } from "../src/api";

export default function AlertsScreen() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wsOk, setWsOk] = useState(false);

  async function load() {
    try {
      const data = await listAlerts();
      setAlerts(data);
    } catch (e) {
      console.warn("listAlerts failed", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
    const close = openAlertStream(() => {
      setWsOk(true);
      // Refetch on push so we get the canonical AlertOut shape (incl s3_key)
      load();
    });
    return close;
  }, []);

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Link href="/settings" asChild>
              <Pressable hitSlop={12}>
                <Text style={{ color: "#06a", fontSize: 22 }}>⚙</Text>
              </Pressable>
            </Link>
          ),
        }}
      />
      <View style={styles.statusBar}>
        <View style={[styles.dot, { backgroundColor: wsOk ? "#2a2" : "#aaa" }]} />
        <Text style={styles.statusText}>{wsOk ? "Tempo real conectado" : "Aguardando push"}</Text>
      </View>
      {loading ? (
        <ActivityIndicator style={{ marginTop: 32 }} />
      ) : alerts.length === 0 ? (
        <Text style={styles.empty}>Nenhum alerta ainda.</Text>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={(a) => a.id}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
          renderItem={({ item }) => <AlertRow alert={item} />}
        />
      )}
    </View>
  );
}

function AlertRow({ alert }: { alert: Alert }) {
  const created = new Date(alert.created_at);
  const scoreColor = alert.score >= 0.8 ? "#d33" : alert.score >= 0.5 ? "#d80" : "#888";
  return (
    <Link href={{ pathname: "/alert/[id]", params: { id: alert.id, s3_key: alert.s3_key } }} asChild>
      <View style={styles.row}>
        <View style={styles.rowHead}>
          <Text style={styles.title}>{alert.rule_name || alert.preset_type}</Text>
          <Text style={[styles.score, { color: scoreColor }]}>{alert.score.toFixed(2)}</Text>
        </View>
        <Text numberOfLines={2} style={styles.msg}>
          {alert.message}
        </Text>
        <View style={styles.rowFoot}>
          <Text style={styles.meta}>{created.toLocaleString("pt-BR")}</Text>
          <Text style={[styles.status, styles[`status_${alert.status}` as keyof typeof styles]]}>
            {alert.status}
          </Text>
        </View>
      </View>
    </Link>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f6f7f9" },
  statusBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    padding: 8,
    backgroundColor: "#fff",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#ccc",
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 12, color: "#666" },
  empty: { textAlign: "center", color: "#888", marginTop: 64 },
  row: {
    backgroundColor: "#fff",
    margin: 8,
    padding: 12,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#ddd",
  },
  rowHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  title: { fontWeight: "600", fontSize: 15 },
  score: { fontVariant: ["tabular-nums"], fontWeight: "600" },
  msg: { color: "#333", marginTop: 4 },
  rowFoot: { flexDirection: "row", justifyContent: "space-between", marginTop: 8 },
  meta: { color: "#888", fontSize: 12 },
  status: { fontSize: 11, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 999 },
  status_pending: { backgroundColor: "#fed", color: "#a60" },
  status_seen: { backgroundColor: "#def", color: "#06a" },
  status_false_positive: { backgroundColor: "#efe", color: "#060" },
});
