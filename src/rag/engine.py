"""
src/rag/engine.py
=================
Retrieval-Augmented Generation (RAG) Engine for LEWDSS
"Regional Landslide Early Warning & Emergency Response Decision Support System"

Provides:
- Domain knowledge corpus covering geomorphological factors, spatial CV,
  state-space soil saturation modeling (DLM), and NDMA emergency SOPs.
- Pure-Python TF-IDF Vectorizer & Cosine Similarity search without heavy external dependencies.
- Grounded context assembly & evidence-based response generation.
"""

import math
import re
from typing import List, Dict, Any, Optional

STOP_WORDS = {
    'the', 'is', 'in', 'at', 'of', 'on', 'and', 'a', 'to', 'for', 'with', 'as',
    'by', 'that', 'this', 'it', 'from', 'or', 'an', 'be', 'are', 'was', 'were',
    'how', 'what', 'why', 'when', 'where', 'which', 'who', 'whom', 'can', 'do',
    'does', 'did', 'into', 'than', 'then', 'so', 'such', 'their', 'there', 'these',
    'those', 'my', 'your', 'our', 'we', 'you', 'i', 'me', 'about', 'explain', 'tell'
}

DEFAULT_KNOWLEDGE_BASE = [
    {
        "id": "doc-1",
        "title": "Landslide Susceptibility Calculation & Methodology",
        "category": "Core Methodology",
        "content": (
            "Landslide susceptibility estimation evaluates the spatial probability of slope failure occurring in a given "
            "terrain based on local geo-environmental conditioning factors. The standard workflow combines Digital Elevation "
            "Model (DEM) derivatives, geological maps, hydrological indices, land cover, and historical landslide inventory points "
            "inside a GIS or Machine Learning pipeline to generate a continuous Susceptibility Index (0.0 to 1.0), which is then "
            "classified into five zones: Very Low, Low, Moderate, High, and Very High using Natural Breaks (Jenks) or quantile classification."
        )
    },
    {
        "id": "doc-2",
        "title": "Topographic Factors: Slope Angle, Aspect & Elevation",
        "category": "Conditioning Factors",
        "content": (
            "Slope Angle is the single most influential topographic factor controlling shear stress on hillslopes; susceptibility "
            "rises sharply on slopes between 25° and 55°, whereas cliffs above 70° often expose bare bedrock with thin soil cover. "
            "Slope Aspect controls exposure to sunlight, prevailing monsoon winds, drying cycles, and soil moisture retention. "
            "Elevation affects microclimate, freeze-thaw cycles, vegetation density, and orographic rainfall intensity."
        )
    },
    {
        "id": "doc-3",
        "title": "Hydrological Indices: TWI, SPI & Rainfall Triggering",
        "category": "Hydrology & Triggers",
        "content": (
            "Topographic Wetness Index (TWI = ln(a / tan(beta))) quantifies steady-state soil moisture accumulation and pore-water pressure "
            "buildup in convergent hollows; high TWI values indicate saturated zones prone to shallow translational slides. Stream Power Index "
            "(SPI = A * tan(beta)) measures the erosive power of flowing water and toe-undercutting along drainage channels. Rainfall "
            "Intensity-Duration (I-D) thresholds and Antecedent Precipitation Index (API over 7 to 15 days) serve as primary dynamic triggers."
        )
    },
    {
        "id": "doc-4",
        "title": "Lithology, Soil Type & Distance to Tectonic Faults",
        "category": "Geology & Structure",
        "content": (
            "Lithology governs rock mass strength, permeability, and weathering rates. Weak, fractured, or clay-rich formations (such as "
            "weathered shale, phyllite, schist, colluvium, and deeply weathered basalt/granite saprolite) exhibit high landslide susceptibility "
            "compared to massive unfractured quartzite or gneiss. Proximity to geological faults, lineaments, and thrust zones (typically within "
            "0–500 meters) significantly increases slope instability due to intense rock shearing and preferential groundwater seepage."
        )
    },
    {
        "id": "doc-5",
        "title": "Vegetation (NDVI), LULC & Anthropogenic Road Cutting",
        "category": "Land Cover & Human Impact",
        "content": (
            "Normalized Difference Vegetation Index (NDVI) reflects canopy density and root reinforcement; deep-rooted forests increase "
            "soil cohesion and intercept rainfall, whereas low NDVI (< 0.2) bare soil or degraded scrubland faces elevated erosion and "
            "shallow failure risk. Distance to Roads is a critical anthropogenic factor: hillslope road-cutting removes lateral toe support "
            "and concentrates runoff, causing high failure density within 0–150 meters of mountain highways."
        )
    },
    {
        "id": "doc-6",
        "title": "Machine Learning Models for Susceptibility Mapping",
        "category": "Modeling & Algorithms",
        "content": (
            "Commonly used models in Landslide Susceptibility Estimators include: (1) Random Forest (RF) — an ensemble of decision trees "
            "resilient to multicollinearity and capable of ranking factor importance; (2) XGBoost / Gradient Boosting — builds sequential trees "
            "that minimize residual error; (3) Logistic Regression (LR) — provides interpretable linear log-odds coefficients; and "
            "(4) Convolutional Neural Networks (CNN) — extracts spatial neighborhood patterns directly from multi-channel raster patches."
        )
    },
    {
        "id": "doc-7",
        "title": "Model Validation: ROC-AUC & Spatial Cross-Validation",
        "category": "Validation & Accuracy",
        "content": (
            "Model performance is primarily evaluated using the Receiver Operating Characteristic - Area Under the Curve (ROC-AUC). "
            "In geographic applications, standard random K-fold cross-validation causes massive data leakage due to spatial autocorrelation. "
            "Spatial Leave-One-District-Out cross-validation is mandatory to test true generalization across held-out geographical zones."
        )
    },
    {
        "id": "doc-8",
        "title": "Susceptibility Risk Zones: High vs. Very High & Mitigation",
        "category": "Risk Zones & Mitigation",
        "content": (
            "Susceptibility Zones classify terrain hazard levels: Very Low & Low zones feature gentle slopes suitable for standard development. "
            "Moderate zones require site-specific drainage checks before construction. High Susceptibility zones exhibit steep slopes and "
            "require engineered retaining walls, subsurface horizontal drains, and bio-engineering. Very High Susceptibility zones represent "
            "critical hazard corridors where new construction should be prohibited and real-time early warning systems deployed."
        )
    },
    {
        "id": "doc-9",
        "title": "LEWDSS Project Overview & Two Study Regions",
        "category": "LEWDSS Architecture",
        "content": (
            "LEWDSS covers two distinct physiographic zones: Region A (Western Ghats: Wayanad, Idukki, Kodagu) and Region B (Northeast India: "
            "East Sikkim, West Sikkim, East Khasi Hills). Ingests NASA GLC/UGLC 144 verified events, Copernicus 30m DEM, and CHIRPS 0.05° "
            "daily precipitation to compute Relative Landslide Susceptibility Index (RLSI) scores with zero-leakage spatial validation."
        )
    },
    {
        "id": "doc-10",
        "title": "Spatial Cross-Validation & Wayanad Model Generalization",
        "category": "LEWDSS Modeling",
        "content": (
            "L2-regularized Logistic Regression achieved 87.0% generalized spatial recall across within-region holdout folds (ROC-AUC 0.8012, "
            "PR-AUC 0.6341). On Wayanad (Fold A1), it successfully detected 100.0% of documented historical events (18/18) with frozen decision "
            "threshold tau*=0.4400. In contrast, Random Forest suffered leaf probability compression under spatial covariate shift."
        )
    },
    {
        "id": "doc-11",
        "title": "State-Space Modeling: Soil Saturation DLM (Kalman Filter)",
        "category": "State-Space Modeling",
        "content": (
            "LEWDSS implements SoilSaturationDLM, a 1-Dimensional Linear Dynamic State-Space Model and Kalman Filter in src/state_space/dlm.py. "
            "It tracks subterranean soil moisture saturation theta_t driven by daily precipitation P_t: State Equation: theta_t = lambda * theta_{t-1} "
            "+ (1 - lambda) * P_t + w_t. Measurement Equation: y_t = theta_t + v_t. Drainage retention lambda in [0.82, 0.90] models exponential "
            "recession during dry spells and surge under cloudburst deluge, replacing static 15-day sums with physically grounded continuous drainage."
        )
    },
    {
        "id": "doc-12",
        "title": "Operational Decision Threshold tau* & NDMA Standard Operating Procedures",
        "category": "Decision Support & SOPs",
        "content": (
            "The operational decision threshold tau* is calibrated strictly on training folds to maximize F1 subject to achieved training recall "
            ">= 80%. When RLSI exceeds tau*, LEWDSS maps output into 4 alert tiers (Minimal, Advisory, Watch, Warning) paired with NDMA-aligned "
            "Standard Operating Procedures for community evacuation, highway clearing, and DEOC command mobilization. Statutorily, only the "
            "District Disaster Management Authority (DDMA) holds executive evacuation authority."
        )
    }
]


def tokenize(text: str) -> List[str]:
    """Tokenize and stem basic terms for geospatial domain matching."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', ' ', text)
    tokens = text.split()
    clean = []
    for w in tokens:
        if len(w) > 1 and w not in STOP_WORDS:
            if w.endswith('ing') and len(w) > 5:
                w = w[:-3]
            elif w.endswith('ies') and len(w) > 4:
                w = w[:-3] + 'y'
            elif w.endswith('es') and len(w) > 4:
                w = w[:-2]
            elif w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
                w = w[:-1]
            clean.append(w)
    return clean


class RAGEngine:
    """Retrieval-Augmented Generation Engine with pure-Python TF-IDF & Cosine Similarity."""

    def __init__(self, knowledge_base: Optional[List[Dict[str, Any]]] = None):
        self.corpus = knowledge_base or list(DEFAULT_KNOWLEDGE_BASE)
        self._build_index()

    def _build_index(self):
        """Index the knowledge chunks into TF-IDF representation."""
        self.N = len(self.corpus)
        self.doc_tokens = []
        self.df = {}

        for doc in self.corpus:
            combined = f"{doc.get('title', '')} {doc.get('title', '')} {doc.get('category', '')} {doc.get('content', '')}"
            tokens = tokenize(combined)
            self.doc_tokens.append(tokens)
            for t in set(tokens):
                self.df[t] = self.df.get(t, 0) + 1

        self.idf = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.N + 1) / (freq + 0.5)) + 1.0

    def add_document(self, title: str, category: str, content: str) -> str:
        """Add a custom project document chunk to the knowledge base."""
        doc_id = f"custom-{len(self.corpus) + 1}"
        self.corpus.append({
            "id": doc_id,
            "title": title,
            "category": category or "Custom Study Area",
            "content": content
        })
        self._build_index()
        return doc_id

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve the top-K relevant knowledge chunks using TF-IDF Cosine Similarity."""
        query_tokens = tokenize(query)
        if not query_tokens or self.N == 0:
            return [{"doc": d, "score": 0.15} for d in self.corpus[:top_k]]

        # Compute query vector
        q_tf = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        q_vec = {}
        q_norm_sq = 0.0
        for t, count in q_tf.items():
            w = (1.0 + math.log(count)) * (self.idf.get(t, math.log(self.N + 1) + 1.0))
            q_vec[t] = w
            q_norm_sq += w * w
        q_norm = math.sqrt(q_norm_sq) or 1.0

        # Score documents
        scored = []
        for idx, doc in enumerate(self.corpus):
            tokens = self.doc_tokens[idx]
            d_tf = {}
            for t in tokens:
                d_tf[t] = d_tf.get(t, 0) + 1

            dot = 0.0
            d_norm_sq = 0.0
            for t, count in d_tf.items():
                w = (1.0 + math.log(count)) * (self.idf.get(t, 1.0))
                d_norm_sq += w * w
                if t in q_vec:
                    dot += w * q_vec[t]
            d_norm = math.sqrt(d_norm_sq) or 1.0

            similarity = dot / (q_norm * d_norm)
            scored.append({"doc": doc, "score": similarity})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def answer_query(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Perform grounded RAG response synthesis."""
        chunks = self.retrieve(query, top_k=top_k)
        if not chunks:
            return {
                "query": query,
                "answer": "No relevant documents found in the local knowledge base.",
                "retrieved_sources": []
            }

        primary = chunks[0]["doc"]
        secondary = chunks[1]["doc"] if len(chunks) > 1 else None

        answer = f"Based on verified project knowledge from **{primary['title']}** (*{primary['category']}*):\n\n{primary['content']}"
        if secondary and chunks[1]["score"] > 0.08:
            answer += f"\n\n**Additional Corroborating Context ({secondary['title']}):**\n{secondary['content']}"

        return {
            "query": query,
            "answer": answer,
            "retrieved_sources": [
                {
                    "title": c["doc"]["title"],
                    "category": c["doc"]["category"],
                    "relevance_score": round(float(c["score"]), 3),
                    "content_snippet": c["doc"]["content"][:200] + "..."
                }
                for c in chunks
            ]
        }
