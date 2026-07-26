"""
RAGAS Evaluation Pipeline for NyayaMitra RAG system.
Evaluates retrieval and generation quality using golden QA pairs.
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Golden Dataset — 30+ QA pairs covering Indian legal topics
# ---------------------------------------------------------------------------
GOLDEN_DATASET = [
    {"question": "What are my rights if police arrest me without a warrant?",
     "ground_truth": "Under CrPC Section 41, police can arrest without warrant only in specific cognizable offence situations. The arrested person has rights under Article 22: right to know grounds of arrest, right to consult a lawyer, right to be produced before magistrate within 24 hours.",
     "context_keywords": ["CrPC", "Section 41", "warrant", "arrest", "Article 22"]},
    {"question": "How do I file an FIR at the police station?",
     "ground_truth": "Under CrPC Section 154, any person can file an FIR for a cognizable offence. The police officer must register the FIR and provide a free copy. If police refuse, complaint can be sent to Superintendent of Police or Judicial Magistrate under Section 156(3).",
     "context_keywords": ["FIR", "Section 154", "cognizable", "Section 156"]},
    {"question": "What is the process for getting bail in India?",
     "ground_truth": "Bail can be obtained under CrPC Sections 436-439. For bailable offences, bail is a right under Section 436. For non-bailable offences, bail is at court's discretion under Section 437. Anticipatory bail is under Section 438.",
     "context_keywords": ["bail", "Section 436", "Section 437", "Section 438", "bailable"]},
    {"question": "What are consumer rights under Consumer Protection Act?",
     "ground_truth": "Consumer Protection Act 2019 provides six rights: right to safety, right to be informed, right to choose, right to be heard, right to seek redressal, and right to consumer education. Complaints can be filed in District, State, or National Commission based on value.",
     "context_keywords": ["Consumer Protection Act", "2019", "rights", "redressal", "Commission"]},
    {"question": "How to file an RTI application?",
     "ground_truth": "Under RTI Act 2005, any citizen can request information from public authorities. Application must be in writing to the Public Information Officer (PIO) with Rs. 10 fee. Response must be given within 30 days. First appeal to First Appellate Authority, second appeal to Information Commission.",
     "context_keywords": ["RTI", "2005", "PIO", "30 days", "Information Commission"]},
    {"question": "What are tenant rights if landlord tries illegal eviction?",
     "ground_truth": "Tenants are protected under state Rent Control Acts. Landlord cannot evict without court order. Grounds for eviction include non-payment of rent, subletting, misuse. Tenant can file complaint for illegal eviction. Essential services cannot be cut off.",
     "context_keywords": ["tenant", "eviction", "Rent Control", "court order"]},
    {"question": "What legal protection exists for domestic violence victims?",
     "ground_truth": "Protection of Women from Domestic Violence Act 2005 provides protection orders, residence orders, monetary relief, custody orders. Victim can file complaint with Protection Officer or police. Magistrate must dispose within 60 days.",
     "context_keywords": ["Domestic Violence", "2005", "protection order", "residence order", "Protection Officer"]},
    {"question": "What are employee rights regarding unpaid wages?",
     "ground_truth": "Payment of Wages Act 1936 ensures timely payment. Wages must be paid before 7th/10th of month. Unauthorized deductions are prohibited under Section 7. Employee can file complaint before Labour Commissioner. Minimum Wages Act ensures minimum payment.",
     "context_keywords": ["Payment of Wages", "Section 7", "Labour Commissioner", "Minimum Wages"]},
    {"question": "How does anticipatory bail work in India?",
     "ground_truth": "Under CrPC Section 438, a person apprehending arrest can apply for anticipatory bail before High Court or Sessions Court. Court considers nature of accusation, background of applicant, and possibility of fleeing justice. Conditions may be imposed.",
     "context_keywords": ["anticipatory bail", "Section 438", "High Court", "Sessions Court"]},
    {"question": "What is the procedure for filing a civil suit?",
     "ground_truth": "Civil suits are filed under Code of Civil Procedure 1908. Plaint must be filed in court with jurisdiction. Court fee must be paid. Defendant is served summons. Stages include written statement, framing of issues, evidence, arguments, and judgment.",
     "context_keywords": ["civil suit", "CPC", "plaint", "jurisdiction", "written statement"]},
    {"question": "What are the grounds for divorce in India?",
     "ground_truth": "Under Hindu Marriage Act Section 13, grounds include cruelty, adultery, desertion for 2 years, conversion, unsoundness of mind, communicable disease. Mutual consent divorce under Section 13B requires 1 year separation. Special Marriage Act has similar provisions.",
     "context_keywords": ["divorce", "Section 13", "cruelty", "mutual consent", "Section 13B"]},
    {"question": "How to file a complaint against medical negligence?",
     "ground_truth": "Medical negligence complaints can be filed under Consumer Protection Act in consumer forums, criminal complaint under IPC Section 304A for death or Section 337/338 for injuries, or civil suit for damages. Indian Medical Council can also take action.",
     "context_keywords": ["medical negligence", "Section 304A", "Consumer Protection", "damages"]},
    {"question": "What are the rights of arrested juveniles?",
     "ground_truth": "Juvenile Justice Act 2015 protects children in conflict with law. No child below 18 to be kept in jail. Must be sent to Juvenile Justice Board. Special provisions for children aged 16-18 for heinous offences. Right to legal aid and privacy.",
     "context_keywords": ["Juvenile Justice", "2015", "Juvenile Justice Board", "legal aid"]},
    {"question": "What is the process for property registration in India?",
     "ground_truth": "Property registration is governed by Registration Act 1908. Sale deed must be registered at Sub-Registrar office. Stamp duty varies by state. Documents needed include sale deed, ID proof, photographs. Registration must be done within 4 months of execution.",
     "context_keywords": ["Registration Act", "1908", "Sub-Registrar", "stamp duty", "sale deed"]},
    {"question": "How to file a cyber crime complaint?",
     "ground_truth": "Cyber crimes are covered under IT Act 2000. Complaints can be filed at cybercrime.gov.in portal, local police station, or Cyber Crime Cell. Section 66 covers hacking, Section 66C covers identity theft, Section 67 covers obscene content.",
     "context_keywords": ["IT Act", "2000", "cyber crime", "Section 66", "hacking"]},
    {"question": "What are the legal remedies for cheque bounce?",
     "ground_truth": "Under Negotiable Instruments Act Section 138, cheque bounce is a criminal offence. Payee must send demand notice within 30 days. If not paid within 15 days of notice, complaint must be filed within 30 days. Punishment includes imprisonment up to 2 years or fine.",
     "context_keywords": ["Section 138", "cheque bounce", "Negotiable Instruments", "demand notice"]},
    {"question": "What are maternity benefits for working women?",
     "ground_truth": "Maternity Benefit Act 1961 (amended 2017) provides 26 weeks paid leave for first two children, 12 weeks for third child. Applicable to establishments with 10+ employees. Work from home option available. Creche facility mandatory for 50+ employees.",
     "context_keywords": ["Maternity Benefit", "26 weeks", "paid leave", "creche"]},
    {"question": "How does the Motor Vehicles Act handle accidents?",
     "ground_truth": "Motor Vehicles Act 2019 covers accident claims. Hit and run compensation increased. Third party insurance mandatory. Claims filed before Motor Accident Claims Tribunal. Compensation based on age, income, and multiplier method. Golden hour treatment mandatory.",
     "context_keywords": ["Motor Vehicles Act", "2019", "accident", "Claims Tribunal", "insurance"]},
    {"question": "What is the Right to Education in India?",
     "ground_truth": "Right to Education Act 2009 under Article 21A provides free and compulsory education for children aged 6-14. 25% reservation in private schools for economically weaker sections. No detention policy up to class 8. Pupil-teacher ratio mandated.",
     "context_keywords": ["RTE", "2009", "Article 21A", "6-14", "25%"]},
    {"question": "What are the laws against dowry in India?",
     "ground_truth": "Dowry Prohibition Act 1961 makes giving and taking dowry punishable with minimum 5 years imprisonment. IPC Section 498A covers cruelty by husband. Section 304B covers dowry death with minimum 7 years punishment. Burden of proof on accused in dowry death cases.",
     "context_keywords": ["Dowry Prohibition", "Section 498A", "Section 304B", "dowry death"]},
    {"question": "How to get a succession certificate?",
     "ground_truth": "Succession certificate is obtained under Indian Succession Act 1925 Section 372. Application filed in District Court where deceased resided. Court issues notice to interested parties. Certificate authorizes collection of debts and securities. Applicable to all religions for movable property.",
     "context_keywords": ["succession certificate", "Section 372", "District Court", "Indian Succession Act"]},
    {"question": "What are the penalties for drunk driving?",
     "ground_truth": "Under Motor Vehicles Act Section 185, first offence attracts imprisonment up to 6 months or fine up to Rs 10,000. Second offence within 3 years attracts imprisonment up to 2 years or fine up to Rs 15,000. License can be suspended or cancelled.",
     "context_keywords": ["drunk driving", "Section 185", "Motor Vehicles Act", "imprisonment"]},
    {"question": "What is the process for adoption in India?",
     "ground_truth": "Hindu Adoption and Maintenance Act governs Hindu adoption. CARA (Central Adoption Resource Authority) handles inter-country and regulated adoption. Juvenile Justice Act allows adoption by all religions. Prospective parents must register on CARA portal.",
     "context_keywords": ["adoption", "CARA", "Juvenile Justice", "Hindu Adoption"]},
    {"question": "How to file a sexual harassment complaint at workplace?",
     "ground_truth": "Under POSH Act 2013, every organization with 10+ employees must have Internal Complaints Committee. Complaint must be filed within 3 months of incident. Committee must complete inquiry within 90 days. Employer failure attracts Rs 50,000 fine.",
     "context_keywords": ["POSH", "2013", "Internal Complaints Committee", "sexual harassment"]},
    {"question": "What are the rules for police interrogation?",
     "ground_truth": "Under CrPC Section 161, police can examine witnesses. Section 162 prohibits signed statements. Confession to police is inadmissible under Evidence Act Section 25. DK Basu guidelines mandate: arrest memo, medical examination, informing family, no torture.",
     "context_keywords": ["Section 161", "Section 162", "confession", "DK Basu"]},
    {"question": "What legal action can be taken for defamation?",
     "ground_truth": "Defamation can be criminal under IPC Sections 499-500 (punishment up to 2 years) or civil (suit for damages). Truth is a defence if published for public good. Nine exceptions under Section 499. Criminal defamation requires complaint to Magistrate.",
     "context_keywords": ["defamation", "Section 499", "Section 500", "damages"]},
    {"question": "How does the POCSO Act protect children?",
     "ground_truth": "POCSO Act 2012 protects children under 18 from sexual offences. Defines penetrative and non-penetrative assault, sexual harassment, and pornography. Special courts for speedy trial. Burden of proof on accused. Mandatory reporting of offences.",
     "context_keywords": ["POCSO", "2012", "sexual offences", "special courts"]},
    {"question": "What are the legal provisions for senior citizen welfare?",
     "ground_truth": "Maintenance and Welfare of Parents and Senior Citizens Act 2007 allows seniors to claim maintenance from children. Maintenance Tribunal can order up to Rs 10,000 per month. Transfer of property by senior citizen can be declared void if done under coercion.",
     "context_keywords": ["senior citizen", "2007", "maintenance", "Maintenance Tribunal"]},
    {"question": "What is the procedure for obtaining a legal heir certificate?",
     "ground_truth": "Legal heir certificate is issued by Tehsildar or Revenue Authority. Application with death certificate, family details submitted. Verification through local inquiry. Used for claiming dues, insurance, pension of deceased. Different from succession certificate.",
     "context_keywords": ["legal heir", "Tehsildar", "death certificate", "Revenue Authority"]},
    {"question": "What are the remedies for land encroachment?",
     "ground_truth": "Land encroachment remedies include filing civil suit for possession, police complaint under IPC Section 441 (criminal trespass), approaching revenue authorities, filing writ petition if government land. Specific Relief Act provides injunction remedies.",
     "context_keywords": ["encroachment", "Section 441", "trespass", "Specific Relief Act", "injunction"]},
    {"question": "What is the process for filing a PIL?",
     "ground_truth": "Public Interest Litigation can be filed in High Court under Article 226 or Supreme Court under Article 32. No court fee required. Any citizen can file for public cause. Court can take suo motu cognizance. Letter petition also accepted.",
     "context_keywords": ["PIL", "Article 226", "Article 32", "public interest"]},
]


class EvaluationPipeline:
    """RAGAS-based evaluation pipeline for NyayaMitra RAG system."""

    def __init__(self):
        self.golden_dataset = GOLDEN_DATASET

    def run_full_eval(self) -> Dict:
        """Run all golden questions through the citizen pipeline and compute metrics."""
        from ..services.citizen_graph import invoke_citizen_pipeline

        logger.info(f"Starting full evaluation with {len(self.golden_dataset)} questions...")
        results = []
        start_time = time.time()

        for i, item in enumerate(self.golden_dataset):
            logger.info(f"Evaluating question {i+1}/{len(self.golden_dataset)}: {item['question'][:50]}...")
            try:
                pipeline_result = invoke_citizen_pipeline(item["question"])
                answer = pipeline_result.get("answer", "")
                sources = pipeline_result.get("sources", [])
                pipeline_log = pipeline_result.get("pipeline_log", [])

                # Extract retrieved contexts from pipeline log
                contexts = []
                for entry in pipeline_log:
                    if entry.get("node") in ("hybrid_retrieve", "rerank"):
                        contexts.append(str(entry))

                result_entry = {
                    "question": item["question"],
                    "ground_truth": item["ground_truth"],
                    "generated_answer": answer,
                    "contexts": contexts,
                    "sources": sources,
                    "context_keywords": item["context_keywords"],
                    "metrics": self._compute_metrics(
                        question=item["question"],
                        answer=answer,
                        ground_truth=item["ground_truth"],
                        context_keywords=item["context_keywords"],
                    ),
                }
                results.append(result_entry)

            except Exception as e:
                logger.error(f"Evaluation failed for question {i+1}: {e}")
                results.append({
                    "question": item["question"],
                    "error": str(e),
                    "metrics": {"faithfulness": 0.0, "answer_relevancy": 0.0,
                                "context_precision": 0.0, "context_recall": 0.0},
                })

        elapsed = time.time() - start_time

        # Aggregate metrics
        summary = self._aggregate_metrics(results)
        summary["total_time_seconds"] = round(elapsed, 2)
        summary["num_questions"] = len(self.golden_dataset)
        summary["per_question"] = results
        summary["timestamp"] = datetime.now().isoformat()

        # Flag problem queries
        summary["problem_queries"] = [
            r["question"] for r in results
            if r.get("metrics", {}).get("faithfulness", 1.0) < 0.6
        ]

        logger.info(f"Evaluation completed in {elapsed:.2f}s")
        return summary

    def _compute_metrics(self, question: str, answer: str, ground_truth: str,
                         context_keywords: List[str]) -> Dict:
        """Compute RAGAS-style metrics for a single QA pair."""
        # Faithfulness: check if answer claims are grounded (keyword overlap heuristic)
        answer_lower = answer.lower()
        ground_lower = ground_truth.lower()

        # Simple faithfulness: how many ground truth keywords appear in answer
        keyword_hits = sum(1 for kw in context_keywords if kw.lower() in answer_lower)
        faithfulness = keyword_hits / len(context_keywords) if context_keywords else 0.0

        # Answer relevancy: does the answer address the question (word overlap)
        q_words = set(question.lower().split())
        a_words = set(answer_lower.split())
        overlap = len(q_words & a_words)
        relevancy = min(1.0, overlap / max(len(q_words), 1) * 2)

        # Context precision: are ground truth keywords present (proxy)
        context_precision = faithfulness  # Same proxy for offline eval

        # Context recall: how much of ground truth is captured
        gt_words = set(ground_lower.split())
        recall_overlap = len(gt_words & a_words)
        context_recall = min(1.0, recall_overlap / max(len(gt_words), 1) * 2)

        return {
            "faithfulness": round(faithfulness, 4),
            "answer_relevancy": round(relevancy, 4),
            "context_precision": round(context_precision, 4),
            "context_recall": round(context_recall, 4),
        }

    def _aggregate_metrics(self, results: List[Dict]) -> Dict:
        """Aggregate per-question metrics into summary statistics."""
        metrics_keys = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        summary = {}

        for key in metrics_keys:
            values = [r.get("metrics", {}).get(key, 0.0) for r in results if "metrics" in r]
            if values:
                summary[f"avg_{key}"] = round(sum(values) / len(values), 4)
                summary[f"min_{key}"] = round(min(values), 4)
                summary[f"max_{key}"] = round(max(values), 4)
            else:
                summary[f"avg_{key}"] = 0.0

        return summary

    def run_retrieval_eval(self) -> Dict:
        """Compare hybrid retrieval vs FAISS-only retrieval."""
        from ..services.vector_service import _get_citizen_vs, _get_citizen_retriever

        logger.info("Running retrieval comparison: Hybrid vs FAISS-only...")
        citizen_vs = _get_citizen_vs()
        hybrid_retriever = _get_citizen_retriever()

        if not citizen_vs:
            return {"error": "Citizen vectorstore not available"}

        comparison = []
        for item in self.golden_dataset[:10]:  # Use subset for speed
            q = item["question"]
            keywords = item["context_keywords"]

            # FAISS-only
            try:
                faiss_docs = citizen_vs.similarity_search(q, k=5)
                faiss_text = " ".join([d.page_content.lower() for d in faiss_docs])
                faiss_hits = sum(1 for kw in keywords if kw.lower() in faiss_text)
                faiss_precision = faiss_hits / len(keywords) if keywords else 0
            except Exception:
                faiss_precision = 0

            # Hybrid
            try:
                hybrid_docs = hybrid_retriever.retrieve(q, k=5)
                hybrid_text = " ".join([d.page_content.lower() for d in hybrid_docs])
                hybrid_hits = sum(1 for kw in keywords if kw.lower() in hybrid_text)
                hybrid_precision = hybrid_hits / len(keywords) if keywords else 0
            except Exception:
                hybrid_precision = 0

            comparison.append({
                "question": q,
                "faiss_precision": round(faiss_precision, 4),
                "hybrid_precision": round(hybrid_precision, 4),
                "improvement": round(hybrid_precision - faiss_precision, 4),
            })

        avg_improvement = sum(c["improvement"] for c in comparison) / len(comparison) if comparison else 0

        return {
            "comparison": comparison,
            "avg_faiss_precision": round(sum(c["faiss_precision"] for c in comparison) / len(comparison), 4),
            "avg_hybrid_precision": round(sum(c["hybrid_precision"] for c in comparison) / len(comparison), 4),
            "avg_improvement": round(avg_improvement, 4),
        }

    def generate_eval_report(self, results: Dict) -> str:
        """Save evaluation report as JSON and return file path."""
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "data", "eval_reports"
        )
        os.makedirs(reports_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(reports_dir, f"report_{timestamp}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Evaluation report saved to {filepath}")

        # Print summary table
        print("\n" + "=" * 60)
        print("  NyayaMitra RAG Evaluation Report")
        print("=" * 60)
        print(f"  Questions evaluated: {results.get('num_questions', 'N/A')}")
        print(f"  Total time: {results.get('total_time_seconds', 'N/A')}s")
        print("-" * 60)
        print(f"  Avg Faithfulness:      {results.get('avg_faithfulness', 'N/A')}")
        print(f"  Avg Answer Relevancy:  {results.get('avg_answer_relevancy', 'N/A')}")
        print(f"  Avg Context Precision: {results.get('avg_context_precision', 'N/A')}")
        print(f"  Avg Context Recall:    {results.get('avg_context_recall', 'N/A')}")
        print("-" * 60)

        problem = results.get("problem_queries", [])
        if problem:
            print(f"  ⚠️ Problem queries (faithfulness < 0.6): {len(problem)}")
            for pq in problem[:5]:
                print(f"    - {pq[:70]}...")
        else:
            print("  ✅ No problem queries detected")
        print("=" * 60 + "\n")

        return filepath

    @staticmethod
    def compare_before_after(baseline_path: str, new_path: str) -> Dict:
        """Compare two evaluation reports."""
        with open(baseline_path, "r") as f:
            baseline = json.load(f)
        with open(new_path, "r") as f:
            new = json.load(f)

        metrics = ["avg_faithfulness", "avg_answer_relevancy", "avg_context_precision", "avg_context_recall"]
        comparison = {}

        print("\n" + "=" * 60)
        print("  Before/After Comparison")
        print("=" * 60)

        for m in metrics:
            old_val = baseline.get(m, 0)
            new_val = new.get(m, 0)
            diff = new_val - old_val
            direction = "↑" if diff > 0 else "↓" if diff < 0 else "→"

            comparison[m] = {"baseline": old_val, "new": new_val, "diff": round(diff, 4), "direction": direction}
            print(f"  {m:30s} {old_val:.4f} → {new_val:.4f}  {direction} {abs(diff):.4f}")

        print("=" * 60 + "\n")
        return comparison
