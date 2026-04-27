"""Create synthetic sample files for local development."""

from pathlib import Path


def main() -> None:
    """Generate dummy sample data files."""
    policy_dir = Path("data/sample_policies")
    history_dir = Path("data/sample_design_history")
    policy_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    (policy_dir / "sample_policy_001.txt").write_text(
        "제1조(목적) 본 문서는 synthetic sample 약관입니다.", encoding="utf-8"
    )
    (history_dir / "sample_design_history.csv").write_text(
        "age_group,gender,product_name,rider\n40s,male,Sample Care Plan,암진단특약\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
