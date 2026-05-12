import { useState } from "react";
import { View, Text, ScrollView, TouchableOpacity, Alert, StyleSheet, Linking } from "react-native";
import { router } from "expo-router";
import { deleteAccount, requestDataExport } from "../src/api";

export default function PrivacyScreen() {
  const [loading, setLoading] = useState(false);

  async function handleExport() {
    try {
      setLoading(true);
      await requestDataExport();
      Alert.alert("Exportação solicitada", "Você receberá um link por e-mail em instantes.");
    } catch (e: any) {
      Alert.alert("Erro", e.message || "Não foi possível solicitar exportação.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    Alert.alert(
      "Excluir conta",
      "Sua conta será permanentemente excluída após 30 dias. Esta ação pode ser desfeita dentro do prazo via suporte.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Excluir conta",
          style: "destructive",
          onPress: async () => {
            try {
              setLoading(true);
              await deleteAccount();
              Alert.alert("Conta marcada para exclusão", "Acesse o painel web para cancelar dentro de 30 dias.");
              router.replace("/");
            } catch (e: any) {
              Alert.alert("Erro", e.message || "Não foi possível excluir conta.");
            } finally {
              setLoading(false);
            }
          },
        },
      ]
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Privacidade & Dados</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Seus direitos (LGPD art. 18)</Text>
        <Text style={styles.body}>
          Você pode exportar todos os seus dados ou solicitar a exclusão da conta a qualquer momento.
        </Text>
      </View>

      <TouchableOpacity
        style={[styles.button, styles.buttonSecondary]}
        onPress={handleExport}
        disabled={loading}
      >
        <Text style={styles.buttonSecondaryText}>Exportar meus dados</Text>
      </TouchableOpacity>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Política de Privacidade</Text>
        <TouchableOpacity
          onPress={() => Linking.openURL("https://cams-erp-web.pages.dev/legal/privacidade")}
        >
          <Text style={styles.link}>Ver política completa ↗</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Aviso de monitoramento</Text>
        <TouchableOpacity
          onPress={() => Linking.openURL("https://cams-erp-web.pages.dev/legal/aviso")}
        >
          <Text style={styles.link}>Baixar cartaz para afixação ↗</Text>
        </TouchableOpacity>
      </View>

      <View style={[styles.section, styles.dangerSection]}>
        <Text style={[styles.sectionTitle, styles.dangerTitle]}>Zona de perigo</Text>
        <TouchableOpacity
          style={[styles.button, styles.buttonDanger]}
          onPress={handleDelete}
          disabled={loading}
        >
          <Text style={styles.buttonDangerText}>Excluir minha conta</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f0f0f" },
  content: { padding: 20, gap: 16 },
  title: { fontSize: 22, fontWeight: "700", color: "#fff", marginBottom: 8 },
  section: { backgroundColor: "#1a1a1a", borderRadius: 12, padding: 16, gap: 8 },
  sectionTitle: { fontSize: 14, fontWeight: "600", color: "#aaa", textTransform: "uppercase", letterSpacing: 0.5 },
  body: { fontSize: 14, color: "#ccc", lineHeight: 20 },
  link: { fontSize: 14, color: "#4f8ef7", textDecorationLine: "underline" },
  button: { borderRadius: 10, paddingVertical: 14, paddingHorizontal: 20, alignItems: "center" },
  buttonSecondary: { backgroundColor: "#1e3a5f", marginTop: 4 },
  buttonSecondaryText: { color: "#4f8ef7", fontWeight: "600", fontSize: 15 },
  dangerSection: { borderColor: "#7f1d1d", borderWidth: 1 },
  dangerTitle: { color: "#ef4444" },
  buttonDanger: { backgroundColor: "#7f1d1d" },
  buttonDangerText: { color: "#fca5a5", fontWeight: "600", fontSize: 15 },
});
