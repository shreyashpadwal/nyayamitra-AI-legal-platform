"""
NyayaMitra RAG Evaluation Script — CI quality gate.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --compare reports/baseline.json
"""

import sys
import os
import argparse

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))


def main():
    parser = argparse.ArgumentParser(description="NyayaMitra RAG Evaluation Pipeline")
    parser.add_argument("--compare", type=str, help="Path to baseline report JSON for comparison")
    parser.add_argument("--retrieval-only", action="store_true", help="Run retrieval eval only")
    args = parser.parse_args()

    from app.services.evaluation.eval_pipeline import EvaluationPipeline

    pipeline = EvaluationPipeline()

    if args.retrieval_only:
        print("\n🔍 Running retrieval comparison (Hybrid vs FAISS-only)...\n")
        retrieval_results = pipeline.run_retrieval_eval()

        print("\n" + "=" * 60)
        print("  Retrieval Comparison Results")
        print("=" * 60)
        print(f"  Avg FAISS Precision:  {retrieval_results.get('avg_faiss_precision', 'N/A')}")
        print(f"  Avg Hybrid Precision: {retrieval_results.get('avg_hybrid_precision', 'N/A')}")
        print(f"  Avg Improvement:      {retrieval_results.get('avg_improvement', 'N/A')}")
        print("=" * 60 + "\n")
        sys.exit(0)

    # Full evaluation
    print("\n⚖️ NyayaMitra RAG Full Evaluation\n")
    print("Running all golden questions through citizen pipeline...")
    print("This may take several minutes depending on LLM response times.\n")

    results = pipeline.run_full_eval()
    report_path = pipeline.generate_eval_report(results)

    print(f"\n📄 Report saved to: {report_path}\n")

    # Compare with baseline if provided
    if args.compare:
        if os.path.exists(args.compare):
            print(f"\n📊 Comparing with baseline: {args.compare}\n")
            EvaluationPipeline.compare_before_after(args.compare, report_path)
        else:
            print(f"\n⚠️ Baseline file not found: {args.compare}\n")

    # CI gate: exit with code 1 if faithfulness below threshold
    avg_faithfulness = results.get("avg_faithfulness", 0)
    if avg_faithfulness < 0.7:
        print(f"\n❌ CI GATE FAILED: avg_faithfulness={avg_faithfulness:.4f} < 0.7\n")
        sys.exit(1)
    else:
        print(f"\n✅ CI GATE PASSED: avg_faithfulness={avg_faithfulness:.4f} >= 0.7\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
