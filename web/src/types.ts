export type Offer = "Public" | "Gerico" | "Ambas" | "Nenhuma" | "Revisar" | "";

export type Opportunity = {
  id: string;
  organization: string;
  state: string;
  city: string;
  modality: string;
  publishedAt: string;
  object: string;
  additionalInfo: string;
  estimatedValue: number | null;
  proposalDeadline: string;
  sampleGroup: string;
  offer: Offer;
  reason: string;
};
