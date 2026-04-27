import { useEffect } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { registerForPush } from "../src/push";

export default function RootLayout() {
  useEffect(() => {
    registerForPush().catch((e) => console.warn("push setup failed:", e));
  }, []);

  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#fff" },
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "Alertas" }} />
        <Stack.Screen name="alert/[id]" options={{ title: "Alerta" }} />
        <Stack.Screen name="settings" options={{ title: "Notificações" }} />
      </Stack>
    </>
  );
}
