import { publicApiResult } from "@/lib/api";

export type PublicContact = {
  email: string;
  phone: string;
  address: string;
  office_hours: string;
};

export type PublicFooterSettings = {
  copyright_name: string;
  membership_note: string;
};

export type PublicFeatures = {
  "association-pulse": boolean;
  "public-resources": boolean;
  "public-gallery": boolean;
};

const defaultContact: PublicContact = {
  email: "utagoffice@ug.edu.gh",
  phone: "+233 (0) 24 427 7275",
  address: "University of Ghana, Legon, Accra",
  office_hours: "Monday–Friday, 9:00 AM–6:00 PM",
};

const defaultFooter: PublicFooterSettings = {
  copyright_name: "University of Ghana Branch of UTAG",
  membership_note:
    "Representing teaching and research staff while advancing academic excellence, professional welfare and service to the University community.",
};

const defaultFeatures: PublicFeatures = {
  "association-pulse": true,
  "public-resources": true,
  "public-gallery": true,
};

function stringSetting(
  values: Record<string, unknown>,
  key: string,
  fallback: string,
) {
  const value = values[key];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

export function phoneHref(phone: string) {
  return phone.replace(/\(0\)/g, "").replace(/[^\d+]/g, "");
}

export async function getPublicSite() {
  const [settingsResult, featuresResult] = await Promise.all([
    publicApiResult<Record<string, Record<string, unknown>>>(
      "/api/v1/public/settings",
      {},
    ),
    publicApiResult<PublicFeatures>("/api/v1/public/features", defaultFeatures),
  ]);
  const contact = settingsResult.data["site.contact"] ?? {};
  const footer = settingsResult.data["site.footer"] ?? {};
  return {
    contact: {
      email: stringSetting(contact, "email", defaultContact.email),
      phone: stringSetting(contact, "phone", defaultContact.phone),
      address: stringSetting(contact, "address", defaultContact.address),
      office_hours: stringSetting(
        contact,
        "office_hours",
        defaultContact.office_hours,
      ),
    },
    footer: {
      copyright_name: stringSetting(
        footer,
        "copyright_name",
        defaultFooter.copyright_name,
      ),
      membership_note: stringSetting(
        footer,
        "membership_note",
        defaultFooter.membership_note,
      ),
    },
    features: { ...defaultFeatures, ...featuresResult.data },
    unavailable: settingsResult.unavailable || featuresResult.unavailable,
  };
}
