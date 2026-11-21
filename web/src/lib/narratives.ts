// One-line, executive-safe interpretations of the SHAP features the model
// actually learned. The headline sentence comes from the API's Driver.value;
// this adds the "so what" without inventing a new number.

const NARRATIVES: Record<string, string> = {
  first_response_hours:
    "La rapidità della prima risposta è la leva più forte che il referente controlla. Più lenta del riferimento, abbassa il punteggio.",
  prior_lost_initiatives:
    "Le iniziative perse nella storia recente sono un segnale sul rapporto e abbassano il punteggio.",
  prior_won_initiatives:
    "Le iniziative vinte insieme sono la prova più chiara che l'azienda porta a termine ciò che inizia.",
  days_since_last_initiative:
    "Le lunghe pause tra le iniziative sono il modo in cui il rapporto si raffredda. L'inattività è un sintomo, non l'obiettivo.",
  meetings_before_scoring:
    "Gli incontri svolti sono coinvolgimento reale. Il modello premia il tempo già dedicato al buyer.",
  owner_win_rate_180d:
    "Il tasso di vincita recente del referente fa parte del punteggio: chi gestisce l'iniziativa conta.",
  amount_arr:
    "Le iniziative più grandi sono più difficili da chiudere in questo mondo, quindi la dimensione abbassa la probabilità.",
  discount_pct:
    "Uno sconto proposto più alto è un segnale di attrito. Abbassa il punteggio invece di comprare la vittoria.",
  tickets_90d:
    "L'attrito con l'assistenza negli ultimi 90 giorni è un segnale negativo sul rapporto.",
  nps_last:
    "La salute del rapporto, all'ultima misura, è un segnale positivo quando l'NPS è alto.",
  source:
    "La provenienza dell'iniziativa porta un effetto di tasso base: segnalazioni e partner convertono meglio dell'outbound.",
  region:
    "I tassi base regionali differiscono e il modello tratta la regione come variabile.",
};

export function driverNarrative(feature: string): string {
  return (
    NARRATIVES[feature] ??
    "Questa variabile ha spostato il punteggio con lo stesso modello che ha valutato ogni iniziativa."
  );
}
