// Configurazione del sito. Le variabili VITE_* si impostano in web/.env oppure
// come "Variables" del repository GitHub (vedi .github/workflows/pages.yml).
const env = import.meta.env

export const CONFIG = {
  goal: 1_000_000,
  milestoneStep: 500,
  groupStart: '2025-06-11',
  pintPriceEur: Number(env.VITE_PINT_PRICE_EUR || 5.5),
  refreshSeconds: 60,

  stripeLink: env.VITE_STRIPE_LINK || 'https://buy.stripe.com/dRm8wHbyFdS90ss1Fe6EU00',
  paypalLink: env.VITE_PAYPAL_LINK || '',
  bmcLink: env.VITE_BUYMEACOFFEE_LINK || '',
  monthlyCostsEur: env.VITE_MONTHLY_COSTS_EUR ? Number(env.VITE_MONTHLY_COSTS_EUR) : null,
  donatedThisMonthEur: env.VITE_DONATED_THIS_MONTH_EUR ? Number(env.VITE_DONATED_THIS_MONTH_EUR) : null,
  supporters: String(env.VITE_SUPPORTERS || '').split(',').map((s: string) => s.trim()).filter(Boolean),
}

/** client_reference_id: nel pannello Stripe vedi da quale bottone arriva ogni donazione. */
export function donateUrl(source: string): string {
  const sep = CONFIG.stripeLink.includes('?') ? '&' : '?'
  return `${CONFIG.stripeLink}${sep}client_reference_id=web_${source}`
}
