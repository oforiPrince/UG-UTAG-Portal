import { publicApi } from "@/lib/api";

export type DeliveryCapabilities = {
  email_delivery: boolean;
  sms_delivery: boolean;
};

export const defaultDeliveryCapabilities: DeliveryCapabilities = {
  email_delivery: false,
  sms_delivery: false,
};

export function emailDeliveryAvailable(caps: DeliveryCapabilities) {
  return caps.email_delivery;
}

export function deliveryAvailable(caps: DeliveryCapabilities) {
  return caps.email_delivery || caps.sms_delivery;
}

export async function getDeliveryCapabilities(): Promise<DeliveryCapabilities> {
  return publicApi("/api/v1/public/capabilities", defaultDeliveryCapabilities, {
    revalidate: false,
  });
}
