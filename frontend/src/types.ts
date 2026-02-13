export type Topic = {
  key: string;
  name: string;
  keywords: string[];
  synonyms: string[];
  negative_keywords: string[];
};

export type Publisher = {
  name: string;
  aliases: string[];
  prefixes: string[];
};

export type AppConfigResponse = {
  app: {
    name: string;
    version: string;
    max_records_default: number;
    rows_per_request: number;
    low_coverage_threshold: number;
  };
  topics: Topic[];
  publishers: Publisher[];
};
