import { useState, useEffect } from "react";

const CONSENT_KEY = "cookie_consent_v1";

export type ConsentChoice = {
  essential: boolean;
  preference: boolean;
  analytics: boolean;
};

export function getCookieConsent(): ConsentChoice | null {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function useConsentAnalytics(): boolean {
  const consent = getCookieConsent();
  return consent?.analytics ?? false;
}

interface CookieBannerProps {
  onOpenPrivacy?: () => void;
}

export function CookieBanner({ onOpenPrivacy }: CookieBannerProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!getCookieConsent()) setVisible(true);
  }, []);

  function accept(choice: ConsentChoice) {
    localStorage.setItem(CONSENT_KEY, JSON.stringify(choice));
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border p-4 shadow-lg">
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <p className="text-sm text-muted-foreground flex-1">
          Usamos cookies essenciais e opcionais (preferência de tema, relatórios de erro via Sentry).{" "}
          <button
            onClick={onOpenPrivacy}
            className="underline text-primary hover:text-primary/80"
          >
            Política de Privacidade
          </button>
        </p>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => accept({ essential: true, preference: false, analytics: false })}
            className="px-3 py-1.5 text-sm border border-border rounded-md hover:bg-muted transition-colors"
          >
            Apenas essenciais
          </button>
          <button
            onClick={() => accept({ essential: true, preference: true, analytics: true })}
            className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            Aceitar todos
          </button>
        </div>
      </div>
    </div>
  );
}
