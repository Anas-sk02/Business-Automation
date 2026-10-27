// 19 Standard Industry Templates matching docs/industry-templates.md

export interface IndustryTemplate {
  id: string;
  label: string;
  icon: string;
  defaultKeywords: string[];
  summaryChecks: string;
  signals: Array<{ id: string; label: string; description: string }>;
}

export const STANDARD_OPPORTUNITY_SIGNALS = [
  {
    id: "no_website",
    label: "No website",
    description: "Business operates with only Google Maps presence and no official website",
  },
  {
    id: "mobile_issues",
    label: "Mobile layout issues",
    description: "Website viewport overflows or layout is broken on mobile devices",
  },
  {
    id: "missing_form",
    label: "Missing inquiry form",
    description: "No direct contact, registration, or appointment inquiry form online",
  },
  {
    id: "missing_whatsapp",
    label: "Missing WhatsApp link",
    description: "No direct WhatsApp chat or click-to-message CTA found on page",
  },
  {
    id: "poor_performance",
    label: "Slow load performance",
    description: "Page load time exceeds 3.5s or scores poorly on mobile performance",
  },
  {
    id: "missing_menu_catalog",
    label: "Missing catalog or menu",
    description: "No product, service catalog, or menu available online for browsing",
  },
];

export const INDUSTRY_TEMPLATES: IndustryTemplate[] = [
  {
    id: "coaching_institutes",
    label: "Coaching / Tuition / Education Centers",
    icon: "🏫",
    defaultKeywords: ["coaching classes", "tuition center", "study center"],
    summaryChecks: "We will check: online course listings, admission forms, fee structure, batch schedules, student testimonials, and WhatsApp inquiry.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "clinics",
    label: "Clinics / Hospitals / Doctors",
    icon: "🏥",
    defaultKeywords: ["clinic", "doctor", "healthcare center"],
    summaryChecks: "We will check: online appointment booking, doctor profiles, consultation timings, services list, and location directions.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "restaurants",
    label: "Restaurants / Cafes / Cloud Kitchens",
    icon: "🍕",
    defaultKeywords: ["restaurant", "cafe", "food delivery"],
    summaryChecks: "We will check: online menu with prices, food photos, table booking, direct ordering links, and opening hours.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "gyms",
    label: "Gyms / Fitness Centers / Yoga Studios",
    icon: "🏋️",
    defaultKeywords: ["gym", "fitness center", "yoga classes"],
    summaryChecks: "We will check: membership pricing, class schedules, trial offers, trainer profiles, and facility photos.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "electronics",
    label: "Electronics / Mobile Stores",
    icon: "📱",
    defaultKeywords: ["electronics shop", "mobile store", "gadget store"],
    summaryChecks: "We will check: product catalog, price visibility, repair/service section, EMI options, and WhatsApp order inquiry.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "clothing",
    label: "Clothing / Fashion Boutiques",
    icon: "👔",
    defaultKeywords: ["fashion boutique", "clothing store", "ethnic wear"],
    summaryChecks: "We will check: product gallery, categorized collections, size guides, new arrivals, and social/WhatsApp shopping.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "real_estate",
    label: "Real Estate / Property Dealers",
    icon: "🏠",
    defaultKeywords: ["property dealer", "real estate agent", "flats for sale"],
    summaryChecks: "We will check: property listings, search filters, property photos, pricing details, and lead callback forms.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "salons",
    label: "Salons / Spas / Beauty Parlors",
    icon: "💇",
    defaultKeywords: ["beauty parlor", "hair salon", "spa center"],
    summaryChecks: "We will check: online appointment booking, service menu with prices, bridal packages, and stylist portfolio.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "hotels",
    label: "Hotels / Homestays / Resorts",
    icon: "🏨",
    defaultKeywords: ["hotel", "homestay", "resort"],
    summaryChecks: "We will check: direct room booking, room gallery, amenities list, location directions, and customer reviews.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "manufacturers",
    label: "Manufacturers / Wholesalers",
    icon: "🏭",
    defaultKeywords: ["manufacturer", "wholesaler", "supplier"],
    summaryChecks: "We will check: product catalog, MOQ information, facility photos, export details, and bulk RFQ inquiry forms.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "repair_services",
    label: "Repair / Service Centers",
    icon: "🔧",
    defaultKeywords: ["repair center", "service center", "appliance repair"],
    summaryChecks: "We will check: service categories, repair pricing, online doorstep booking, warranty policies, and brands serviced.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "auto_dealers",
    label: "Car Dealers / Auto Service",
    icon: "🚗",
    defaultKeywords: ["car dealer", "used cars", "auto service center"],
    summaryChecks: "We will check: vehicle inventory, test drive booking, service scheduling, EMI calculator, and vehicle photos.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "pharmacies",
    label: "Pharmacies / Medical Stores",
    icon: "💊",
    defaultKeywords: ["pharmacy", "medical store", "chemist"],
    summaryChecks: "We will check: online medicine ordering, prescription upload, home delivery info, and store timings.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "schools",
    label: "Schools / Colleges",
    icon: "🎓",
    defaultKeywords: ["school", "college", "international school"],
    summaryChecks: "We will check: admission portal, fee structure, academic curriculum, campus gallery, and contact information.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "legal_consulting",
    label: "Lawyers / CAs / Consultants",
    icon: "⚖️",
    defaultKeywords: ["advocate", "chartered accountant", "business consultant"],
    summaryChecks: "We will check: practice areas, professional credentials, consultation booking, case studies, and office hours.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "photography",
    label: "Photography / Videography",
    icon: "📸",
    defaultKeywords: ["wedding photographer", "photo studio", "videographer"],
    summaryChecks: "We will check: portfolio gallery, package pricing, booking inquiries, client testimonials, and equipment showcase.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "finance_insurance",
    label: "Banks / Finance / Insurance",
    icon: "🏦",
    defaultKeywords: ["insurance agent", "loan consultant", "financial advisor"],
    summaryChecks: "We will check: financial products, EMI calculator, branch locator, online application forms, and support links.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "supermarkets",
    label: "General Stores / Supermarkets",
    icon: "🛒",
    defaultKeywords: ["supermarket", "grocery store", "departmental store"],
    summaryChecks: "We will check: product catalog, online ordering, delivery zones, promotional offers, and store contact info.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
  {
    id: "custom",
    label: "Other (Type your own industry)",
    icon: "✨",
    defaultKeywords: [],
    summaryChecks: "We will check: mobile usability, contact forms, page load speed, WhatsApp link, and online visibility.",
    signals: STANDARD_OPPORTUNITY_SIGNALS,
  },
];

export function getIndustryTemplate(id: string): IndustryTemplate {
  const found = INDUSTRY_TEMPLATES.find((t) => t.id === id);
  return found || INDUSTRY_TEMPLATES[INDUSTRY_TEMPLATES.length - 1];
}
