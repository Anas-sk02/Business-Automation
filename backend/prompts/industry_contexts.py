"""Industry-specific domain context and opportunity knowledge base.

Covers the 19 standard industry templates defined in SignalForge AI.
Provides industry expectations, common digital conversion gaps, and high-impact pitch angles.
"""

from typing import Any, Dict, Optional

INDUSTRY_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "coaching_institutes": {
        "label": "Coaching & Education Centers",
        "description": "Local educational academies, competitive exam preparation, and tuition centers.",
        "relevant_checks": [
            "Course and subject offerings",
            "Faculty credentials and past student results/testimonials",
            "Batch timing schedules and fee structures",
            "Direct admission inquiry form or WhatsApp consultation link",
            "Mobile-responsive syllabus downloads",
        ],
        "common_opportunities": [
            "Missing direct WhatsApp enrollment button for parents inquiring from mobile devices",
            "Unclear fee structures or lack of transparent batch schedule details",
            "Slow mobile page load times causing prospective students on cellular connections to drop off",
            "No lead capture form on high-intent course pages",
        ],
        "pitch_angles": [
            "Upgrade your institute's website with 1-click WhatsApp student counseling to double parent inquiry conversions.",
            "Fix mobile responsiveness issues and page speed to capture high-intent students searching for coaching in your city.",
        ],
    },
    "clinics": {
        "label": "Clinics, Doctors & Healthcare Centers",
        "description": "Medical practitioners, dental clinics, specialty healthcare centers, and polyclinics.",
        "relevant_checks": [
            "Specialist qualifications and doctor profiles",
            "Online appointment booking or calendar widget",
            "Clinic consultation hours and emergency contact",
            "Patient reviews, hygienic clinic photos, and hospital tie-ups",
            "Clear clinic address with interactive Google Maps directions",
        ],
        "common_opportunities": [
            "Lack of online appointment booking, forcing patients to call during busy OPD hours",
            "Missing WhatsApp chat widget for quick appointment confirmation and inquiries",
            "Mobile viewport horizontal overflow making doctor timings unreadable on smartphones",
            "Broken internal links to specific treatment or specialty pages",
        ],
        "pitch_angles": [
            "Implement instant online doctor appointment scheduling and WhatsApp booking reminders to reduce missed consultations.",
            "Modernize your clinic's mobile web presence to convert local patient searches into confirmed appointments.",
        ],
    },
    "restaurants": {
        "label": "Restaurants, Cafes & Cloud Kitchens",
        "description": "Dine-in eateries, cafes, bakeries, bars, and delivery kitchens.",
        "relevant_checks": [
            "Mobile-friendly digital menu with clear pricing (not blurry PDF downloads)",
            "High-resolution dish photos and ambiance photography",
            "Table reservation system or direct phone/WhatsApp booking",
            "Operating hours, weekly off-days, and live location directions",
            "Direct ordering integration or links to delivery partners",
        ],
        "common_opportunities": [
            "Menu hidden behind large PDF downloads that fail to open quickly on mobile devices",
            "No direct table reservation or WhatsApp ordering link",
            "Missing structured opening hours causing customers to visit during closed hours",
            "Slow loading times due to uncompressed food imagery",
        ],
        "pitch_angles": [
            "Deploy an interactive mobile menu and WhatsApp table reservation system to capture direct customer orders.",
            "Boost local dining traffic by optimizing your Google Maps visibility and mobile website speed.",
        ],
    },
    "gyms": {
        "label": "Gyms, Fitness Studios & Crossfit Centers",
        "description": "Fitness clubs, yoga centers, personal training studios, and martial arts academies.",
        "relevant_checks": [
            "Membership plans, pricing tiers, and trial workout booking",
            "Trainer bios, certifications, and facility equipment photos",
            "Group class schedules (spinning, yoga, HIIT)",
            "Member transformation stories and reviews",
        ],
        "common_opportunities": [
            "No 1-day free pass or trial booking form on the landing page",
            "Missing WhatsApp chat for instant membership inquiries",
            "Class timetable not optimized for mobile screens",
        ],
        "pitch_angles": [
            "Add a 1-click free trial booking funnel on your website to consistently generate new gym walk-ins.",
            "Enhance mobile speed and membership lead capture to outperform competing gyms in your neighborhood.",
        ],
    },
    "electronics": {
        "label": "Electronics & Appliance Stores",
        "description": "Retail consumer electronics, mobile phone outlets, and home appliance dealers.",
        "relevant_checks": [
            "Product catalog with brand categories and price ranges",
            "In-store stock availability checking and EMI scheme details",
            "Store address, landmark directions, and WhatsApp product inquiry",
        ],
        "common_opportunities": [
            "No online catalog of trending models, losing customers to online marketplaces",
            "Missing WhatsApp consultation for price matching and product availability",
        ],
        "pitch_angles": [
            "Showcase current stock and instant WhatsApp price quotes on your site to draw shoppers into your retail store.",
            "Add mobile-friendly EMI calculators and instant product availability inquiries to close local buyers before they shop online.",
        ],
    },
    "clothing": {
        "label": "Clothing Boutiques & Apparel Stores",
        "description": "Fashion boutiques, ethnic wear showrooms, and bespoke tailoring outlets.",
        "relevant_checks": [
            "Lookbook gallery and seasonal collection previews",
            "Custom fitting and alteration consultation booking",
            "Customer testimonials and boutique video tours",
        ],
        "common_opportunities": [
            "High-resolution lookbook images slowing down mobile page load beyond 4 seconds",
            "No direct WhatsApp inquiry on featured bridal or designer outfits",
        ],
        "pitch_angles": [
            "Turn casual social and search browsers into showroom visits with an ultra-fast mobile catalog and WhatsApp styling support.",
            "Enable 1-tap WhatsApp fitting appointments and bridal consultations to maximize high-ticket boutique walk-ins.",
        ],
    },
    "real_estate": {
        "label": "Real Estate Agencies & Property Consultants",
        "description": "Property brokers, real estate developers, and rental management services.",
        "relevant_checks": [
            "Active property listings with photos, floorplans, and pricing",
            "Filterable search by locality, budget, and property type",
            "Site visit scheduling form and WhatsApp brochure delivery",
        ],
        "common_opportunities": [
            "Outdated property listings or broken links on expired projects",
            "Slow load times due to large architectural render files",
            "No automated WhatsApp brochure delivery system",
        ],
        "pitch_angles": [
            "Automate instant property brochure delivery over WhatsApp and capture high-net-worth buyer leads 24/7.",
            "Modernize property listing speeds and mobile virtual tour responsiveness to increase site visit booking rates.",
        ],
    },
    "salons": {
        "label": "Salons, Spas & Beauty Parlors",
        "description": "Hair salons, luxury spas, nail art studios, and aesthetic beauty centers.",
        "relevant_checks": [
            "Transparent service rate card and package combos",
            "Online appointment booking widget with time-slot selection",
            "Stylist portfolios and client transformation gallery",
        ],
        "common_opportunities": [
            "Missing self-service appointment scheduler, requiring manual phone calls during peak styling hours",
            "Menu/rate card published as unreadable mobile images",
        ],
        "pitch_angles": [
            "Implement a sleek online service booking and WhatsApp reminder flow to fill empty mid-week salon chairs.",
            "Publish mobile-optimized rate cards with 1-tap booking to convert local beauty searches into recurring appointments.",
        ],
    },
    "hotels": {
        "label": "Hotels, Resorts & Guest Houses",
        "description": "Boutique hotels, business stays, bed & breakfasts, and holiday resorts.",
        "relevant_checks": [
            "Room categories, amenities, and transparent tariff rates",
            "Direct room booking engine with instant confirmation",
            "Local tourist attractions guide and directions",
        ],
        "common_opportunities": [
            "Heavy reliance on OTAs charging 20% commission due to lack of a direct commission-free booking site",
            "Mobile horizontal layout overflow on room gallery pages",
        ],
        "pitch_angles": [
            "Enable commission-free direct room bookings on your website to retain 100% of guest revenue.",
            "Boost direct guest reservations with a mobile-friendly booking widget and instant WhatsApp inquiry response.",
        ],
    },
    "manufacturers": {
        "label": "Manufacturers & Industrial Suppliers",
        "description": "B2B manufacturing plants, fabrication units, and industrial equipment producers.",
        "relevant_checks": [
            "Technical product specs and downloadable PDF catalogs",
            "Request-for-Quote (RFQ) and bulk inquiry forms",
            "ISO certifications, quality standards, and factory photos",
        ],
        "common_opportunities": [
            "No clear Request-for-Quote (RFQ) form for B2B buyers",
            "Outdated website lacking modern SSL security or mobile compatibility",
        ],
        "pitch_angles": [
            "Upgrade your corporate industrial website to establish B2B credibility and attract domestic and export inquiries.",
            "Implement streamlined RFQ specification forms to convert industrial buyers and procurement managers into qualified inquiries.",
        ],
    },
    "repair_services": {
        "label": "Repair Services & Technicians",
        "description": "Appliance repair, mobile/laptop service centers, and home maintenance pros.",
        "relevant_checks": [
            "List of supported brands and common problem diagnostics",
            "Emergency doorstep service booking and turnaround times",
            "Transparent inspection fees and warranty guarantees",
        ],
        "common_opportunities": [
            "No click-to-call or instant emergency booking link on mobile header",
            "Missing pricing transparency causing customer hesitation",
        ],
        "pitch_angles": [
            "Capture urgent local repair calls with a high-speed mobile landing page and 1-tap call/WhatsApp buttons.",
            "Transparent pricing tables and upfront warranty badges eliminate hesitation and convert emergency service searches into confirmed jobs.",
        ],
    },
    "auto_dealers": {
        "label": "Auto Dealers & Car Showrooms",
        "description": "New car dealerships, certified pre-owned car outlets, and two-wheeler showrooms.",
        "relevant_checks": [
            "Inventory of vehicles with specs, mileage, and prices",
            "Test drive booking form and loan EMI calculators",
            "Trade-in / old vehicle valuation request tool",
        ],
        "common_opportunities": [
            "No interactive test-drive booking or trade-in valuation widget",
            "Slow website load times losing buyers comparing showroom options",
        ],
        "pitch_angles": [
            "Generate pre-qualified test drive and finance leads with interactive calculators and WhatsApp lead capture.",
            "Accelerate vehicle sales inquiries by adding quick trade-in valuation forms and instant WhatsApp window-sticker requests.",
        ],
    },
    "pharmacies": {
        "label": "Pharmacies & Medical Stores",
        "description": "Retail chemist shops, medical supply outlets, and wellness product stores.",
        "relevant_checks": [
            "Home delivery policy and prescription upload via WhatsApp",
            "Store operating hours, night service, and helpline number",
            "Location map with nearest parking and landmark info",
        ],
        "common_opportunities": [
            "No prescription upload via WhatsApp feature for local medicine delivery",
            "Missing emergency night service details on Google listing and site",
        ],
        "pitch_angles": [
            "Launch a 1-tap WhatsApp prescription delivery service to build a recurring neighborhood customer base.",
            "Showcase emergency operating hours and home medicine delivery coverage to capture high-urgency local orders.",
        ],
    },
    "schools": {
        "label": "Schools & Pre-Schools",
        "description": "K-12 schools, international academies, and Montessori daycare centers.",
        "relevant_checks": [
            "Admission procedure, eligibility, and academic calendar",
            "Curriculum overview, sports/extracurricular facilities, and safety measures",
            "Campus virtual tour and prospectus download",
        ],
        "common_opportunities": [
            "No online admission inquiry or prospectus download form",
            "Mobile layout bugs on campus gallery and teacher credential pages",
        ],
        "pitch_angles": [
            "Increase school admissions with an interactive prospectus download and automated WhatsApp counselor callbacks.",
            "Showcase campus facilities and academic achievements on an error-free mobile website to build parent confidence during admission season.",
        ],
    },
    "legal_consulting": {
        "label": "Legal, CA & Corporate Consulting",
        "description": "Law firms, chartered accountants, tax consultants, and company secretaries.",
        "relevant_checks": [
            "Practice areas and specialized legal/tax services",
            "Partner profiles, Bar credentials, and advisory experience",
            "Confidential consultation booking form",
        ],
        "common_opportunities": [
            "Missing consultation request form or unclear professional fee ranges",
            "Outdated non-SSL website eroding professional client trust",
        ],
        "pitch_angles": [
            "Establish firm authority and capture corporate advisory clients with an SSL-secured, high-speed professional web presence.",
            "Add confidential consultation request scheduling to turn high-intent legal searches into retained corporate and individual clients.",
        ],
    },
    "photography": {
        "label": "Photography & Videography Studios",
        "description": "Wedding photographers, commercial studios, and event videographers.",
        "relevant_checks": [
            "Categorized portfolio (weddings, portraits, products)",
            "Event package pricing guides and booking calendar availability",
            "Client testimonials and full gallery delivery samples",
        ],
        "common_opportunities": [
            "Uncompressed portfolio photos causing extreme mobile load times (>6 seconds)",
            "No date availability checker or WhatsApp quote tool",
        ],
        "pitch_angles": [
            "Compress and optimize your portfolio for mobile speeds to double wedding inquiry bookings without losing image quality.",
            "Add an interactive date availability check and WhatsApp quote request to capture couples planning their upcoming events.",
        ],
    },
    "finance_insurance": {
        "label": "Finance, Loans & Insurance Advisors",
        "description": "Personal loan brokers, insurance agents, and wealth management advisors.",
        "relevant_checks": [
            "Loan interest rate tables, insurance coverage comparisons",
            "EMI and eligibility calculators",
            "IRDAI/SEBI credentials and customer claims assistance",
        ],
        "common_opportunities": [
            "No interactive eligibility or premium calculator to capture leads",
            "Unsecure HTTP connection on pages requesting financial details",
        ],
        "pitch_angles": [
            "Deploy custom loan and insurance calculators that deliver instant quotes and qualified buyer leads to your WhatsApp.",
            "Secure your financial lead capture with SSL encryption and clear compliance badges to build trust with high-value borrowers.",
        ],
    },
    "supermarkets": {
        "label": "Supermarkets & Grocery Stores",
        "description": "Independent grocery marts, organic food markets, and gourmet food stores.",
        "relevant_checks": [
            "Weekly discount flyers and seasonal promotional offers",
            "Home delivery radius, minimum order value, and WhatsApp order number",
            "Store address, parking details, and operating timings",
        ],
        "common_opportunities": [
            "No digital catalog of weekly specials or WhatsApp ordering",
            "Missing local delivery radius specifications",
        ],
        "pitch_angles": [
            "Counter quick-commerce competition with regular digital promotional flyers and neighborhood WhatsApp delivery.",
            "Attract high-intent local neighborhood shoppers by highlighting store inventory, discounts, and instant WhatsApp inquiries.",
        ],
    },
    "custom": {
        "label": "Local Commercial Business",
        "description": "Independent local enterprise serving commercial and retail clients.",
        "relevant_checks": [
            "Core services and commercial offerings overview",
            "Transparent pricing or custom quotation request flow",
            "Client reviews, credentials, and work samples",
            "Direct mobile communication channels (phone, WhatsApp, email)",
            "Mobile-responsive navigation and fast page performance",
        ],
        "common_opportunities": [
            "Website lacks responsive mobile optimization, hindering smartphone prospects",
            "Missing direct WhatsApp or 1-tap call communication options",
            "Slow server response and page load times increasing bounce rates",
            "Absence of structured lead capture forms on core offering pages",
        ],
        "pitch_angles": [
            "Modernize your digital presence with high-speed mobile optimization and direct WhatsApp lead generation.",
            "Eliminate conversion bottlenecks on your website to turn local search traffic into paying customers.",
        ],
    },
}

# Aliases mapping shorthand keys to canonical templates
INDUSTRY_ALIASES: Dict[str, str] = {
    "coaching": "coaching_institutes",
    "education": "coaching_institutes",
    "tuition": "coaching_institutes",
    "clinic": "clinics",
    "healthcare": "clinics",
    "doctor": "clinics",
    "dental": "clinics",
    "hospital": "clinics",
    "restaurant": "restaurants",
    "cafe": "restaurants",
    "food": "restaurants",
    "gym": "gyms",
    "fitness": "gyms",
    "electronic": "electronics",
    "appliance": "electronics",
    "apparel": "clothing",
    "fashion": "clothing",
    "realestate": "real_estate",
    "property": "real_estate",
    "salon": "salons",
    "spa": "salons",
    "beauty": "salons",
    "hotel": "hotels",
    "resort": "hotels",
    "manufacturing": "manufacturers",
    "factory": "manufacturers",
    "repair": "repair_services",
    "automobile": "auto_dealers",
    "cars": "auto_dealers",
    "pharmacy": "pharmacies",
    "medical_store": "pharmacies",
    "school": "schools",
    "legal": "legal_consulting",
    "lawyer": "legal_consulting",
    "ca": "legal_consulting",
    "photo": "photography",
    "finance": "finance_insurance",
    "insurance": "finance_insurance",
    "loans": "finance_insurance",
    "grocery": "supermarkets",
    "supermarket": "supermarkets",
}


def get_industry_context(industry_key: Optional[str]) -> str:
    """Retrieve formatted industry context block for prompt construction.

    Normalizes the key and resolves standard templates and aliases.
    Falls back to the 'custom' generic business context if unrecognized.
    """
    normalized = (industry_key or "").lower().strip().replace("-", "_").replace(" ", "_")
    canonical_key = INDUSTRY_ALIASES.get(normalized, normalized)
    data = INDUSTRY_CONTEXTS.get(canonical_key, INDUSTRY_CONTEXTS["custom"])

    checks_bulleted = "\n".join(f"- {c}" for c in data["relevant_checks"])
    opportunities_bulleted = "\n".join(f"- {o}" for o in data["common_opportunities"])
    pitch_bulleted = "\n".join(f"- {p}" for p in data["pitch_angles"])

    return (
        f"Industry Sector: {data['label']}\n"
        f"Sector Profile: {data['description']}\n\n"
        f"Key Digital Assets Expected:\n{checks_bulleted}\n\n"
        f"Typical Digital Gaps:\n{opportunities_bulleted}\n\n"
        f"Recommended Pitch Angles:\n{pitch_bulleted}"
    )
