import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert as RNAlert,
  Button,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Subscriber, createSubscriber, deleteSubscriber, listSubscribers } from "../src/api";

export default function SettingsScreen() {
  const [subs, setSubs] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(true);
  const [phone, setPhone] = useState("");

  async function load() {
    try {
      setSubs(await listSubscribers());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function addPhone() {
    const t = phone.trim();
    if (t.length < 10) {
      RNAlert.alert("Telefone inválido", "Use formato com DDI: 55 11 99999-1234");
      return;
    }
    try {
      await createSubscriber("whatsapp", t);
      setPhone("");
      load();
    } catch (e) {
      RNAlert.alert("Erro", String(e));
    }
  }

  async function remove(id: string) {
    await deleteSubscriber(id);
    load();
  }

  if (loading) return <ActivityIndicator style={{ marginTop: 32 }} />;

  return (
    <View style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.title}>WhatsApp</Text>
        <Text style={styles.help}>
          Adicione um número que receberá os alertas via WhatsApp. Funciona via Evolution API
          local (não precisa Meta API).
        </Text>
        <View style={styles.row}>
          <TextInput
            style={styles.input}
            placeholder="+55 11 99999-1234"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            autoCorrect={false}
          />
          <Button title="Adicionar" onPress={addPhone} />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.title}>Inscritos ({subs.length})</Text>
        <FlatList
          data={subs}
          keyExtractor={(s) => s.id}
          renderItem={({ item }) => (
            <View style={styles.subRow}>
              <Text style={styles.kind}>{item.kind === "whatsapp" ? "WA" : "📱"}</Text>
              <Text style={styles.target} numberOfLines={1}>
                {item.target}
              </Text>
              <Button title="Remover" color="#d33" onPress={() => remove(item.id)} />
            </View>
          )}
          ListEmptyComponent={<Text style={styles.empty}>Nenhum inscrito ainda.</Text>}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  section: { marginBottom: 24 },
  title: { fontSize: 16, fontWeight: "600", marginBottom: 8 },
  help: { color: "#666", marginBottom: 12, fontSize: 13 },
  row: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#aaa",
    borderRadius: 6,
    padding: 8,
  },
  subRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#eee",
  },
  kind: { fontWeight: "600", width: 28 },
  target: { flex: 1, fontFamily: "monospace" },
  empty: { color: "#888", textAlign: "center", padding: 16 },
});
