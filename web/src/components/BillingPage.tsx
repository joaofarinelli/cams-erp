import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";


export function BillingPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header>
        <h2 className="text-xl font-semibold">Plano e cobrança</h2>
        <p className="text-sm text-muted-foreground">
          Em construção. Stripe Checkout + Portal serão habilitados na próxima release.
        </p>
      </header>

      <Card>
        <CardContent className="space-y-3 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Plano atual
            </p>
            <p className="text-lg font-medium">Trial</p>
            <p className="text-xs text-muted-foreground">
              Quotas e cobrança serão expostas aqui assim que o billing entrar em produção.
            </p>
          </div>
          <Button disabled>Gerenciar pagamento</Button>
        </CardContent>
      </Card>
    </div>
  );
}
