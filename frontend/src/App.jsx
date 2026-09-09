import { useState } from "react";
import {
  Camera,
  Upload,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Search,
  Loader2,
  FileText,
  RotateCcw,
} from "lucide-react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function App() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("");

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (selectedFile) => {
    if (!selectedFile) return;

    if (!selectedFile.type.startsWith("image/")) {
      setError("Please select an image file.");
      return;
    }

    setFile(selectedFile);
    setPreview(URL.createObjectURL(selectedFile));
    setResult(null);
    setError("");
  };

  const handleFileChange = (event) => {
    handleFile(event.target.files?.[0]);
    event.target.value = "";
  };

  const getToken = async () => {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        username: "admin@example.com",
        password: "admin123",
      }),
    });

    if (!response.ok) {
      throw new Error("Unable to authenticate with the backend.");
    }

    const data = await response.json();

    if (!data.access_token) {
      throw new Error("Backend did not return an access token.");
    }

    return data.access_token;
  };

  const createInspection = async (token) => {
    const response = await fetch(`${API_BASE}/inspections/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: "PROCESSING",
        ruleset_version: "1.0.0",
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Failed to create inspection.");
    }

    const data = await response.json();

    if (!data.id) {
      throw new Error("Backend did not return an inspection ID.");
    }

    return data.id;
  };

  const uploadImage = async (token, inspectionId) => {
    const formData = new FormData();

    formData.append("images", file);
    formData.append("view_type", "front");

    const response = await fetch(
      `${API_BASE}/inspections/${inspectionId}/images`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Image upload failed.");
    }

    return response.json();
  };

  const analyzeInspection = async (token, inspectionId) => {
    const response = await fetch(
      `${API_BASE}/inspections/${inspectionId}/analyze`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Package analysis failed.");
    }

    return response.json();
  };

  const analyzePackage = async () => {
    if (!file) {
      setError("Please capture or select a package image first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      setStage("Connecting to LEGALENS...");

      const token = await getToken();

      setStage("Creating inspection...");

      const inspectionId = await createInspection(token);

      setStage("Uploading package image...");

      await uploadImage(token, inspectionId);

      setStage("Running OCR and compliance analysis...");

      const analysis = await analyzeInspection(
        token,
        inspectionId
      );

      setStage("");
      setResult(analysis);
    } catch (err) {
      console.error(err);

      setStage("");
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while analyzing the package."
      );
    } finally {
      setLoading(false);
    }
  };

  const resetScan = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError("");
    setStage("");
  };

  const getStatusClass = (status) => {
    if (status === "PASS") return "status-pass";
    if (status === "FAIL") return "status-fail";
    if (
      status === "MANUAL_REVIEW" ||
      status === "REVIEW"
    ) {
      return "status-review";
    }

    return "status-neutral";
  };

  const getOverallClass = (status) => {
    if (status === "COMPLIANT") return "status-pass";
    if (status === "NON_COMPLIANT") return "status-fail";
    return "status-review";
  };

  const getOverallIcon = (status) => {
    if (status === "COMPLIANT") {
      return <CheckCircle2 size={27} />;
    }

    if (status === "NON_COMPLIANT") {
      return <AlertTriangle size={27} />;
    }

    return <Search size={27} />;
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">
            <ShieldCheck size={24} />
          </div>

          <div>
            <h1>LEGALENS</h1>
            <p>Legal Metrology Compliance</p>
          </div>
        </div>

        <div className="ruleset">
          Ruleset v1.0.0
        </div>
      </header>

      <main className="container">
        <section className="hero">
          <span className="eyebrow">
            PACKAGE INSPECTION
          </span>

          <h2>
            Scan a packaged commodity.
            <br />
            Check the declarations.
          </h2>

          <p>
            Capture the package label and LEGALENS will
            extract visible declarations and identify items
            requiring verification.
          </p>
        </section>

        <section className="scanner-card">
          {!preview ? (
            <label className="drop-zone">
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
              />

              <div className="drop-icon">
                <Camera size={32} />
              </div>

              <h3>Scan package</h3>

              <p>
                Take a photo with your camera
                <br />
                or select an existing package image
              </p>

              <span className="upload-button">
                <Upload size={18} />
                Choose image
              </span>
            </label>
          ) : (
            <div className="preview-wrapper">
              <img
                src={preview}
                alt="Selected package"
                className="preview-image"
              />

              <div className="preview-actions">
                <label className="secondary-button">
                  <RotateCcw size={18} />
                  Retake
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handleFileChange}
                  />
                </label>

                <button
                  className="primary-button"
                  onClick={analyzePackage}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2
                        size={18}
                        className="spin"
                      />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <ShieldCheck size={18} />
                      Analyze package
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </section>

        {loading && (
          <section className="processing-card">
            <Loader2 size={24} className="spin" />

            <div>
              <strong>{stage}</strong>
              <p>
                Please keep this page open while the
                package is processed.
              </p>
            </div>
          </section>
        )}

        {error && (
          <section className="error-card">
            <AlertTriangle size={22} />

            <div>
              <strong>Analysis failed</strong>
              <p>{error}</p>
            </div>
          </section>
        )}

        {result && (
          <section className="results">
            <div className="results-header">
              <div>
                <span className="eyebrow">
                  ANALYSIS RESULT
                </span>

                <h2>Compliance assessment</h2>

                <p className="inspection-id">
                  Inspection #{result.inspection_id}
                </p>
              </div>

              <div
                className={`overall-status ${getOverallClass(
                  result.status
                )}`}
              >
                {getOverallIcon(result.status)}

                <div>
                  <span>Overall status</span>
                  <strong>{result.status}</strong>
                </div>
              </div>
            </div>

            <div className="metric-grid">
              <div className="metric-card">
                <span>Compliance score</span>
                <strong>
                  {result.compliance_percentage}%
                </strong>
              </div>

              <div className="metric-card">
                <span>Passed</span>
                <strong>{result.summary.passed}</strong>
              </div>

              <div className="metric-card">
                <span>Manual review</span>
                <strong>
                  {result.summary.manual_review}
                </strong>
              </div>

              <div className="metric-card">
                <span>Confirmed failures</span>
                <strong>{result.summary.failed}</strong>
              </div>
            </div>

            <div className="section-card">
              <div className="section-title">
                <FileText size={19} />
                <h3>Extracted declarations</h3>
              </div>

              <div className="field-grid">
                <Field
                  label="Product name"
                  value={
                    result.extracted_fields.product_name
                  }
                />

                <Field
                  label="MRP"
                  value={
                    result.extracted_fields.mrp !== null &&
                    result.extracted_fields.mrp !== undefined
                      ? `₹${result.extracted_fields.mrp}`
                      : null
                  }
                />

                <Field
                  label="Manufacturing date"
                  value={
                    result.extracted_fields
                      .manufacturing_date
                  }
                />

                <Field
                  label="Use-by date"
                  value={
                    result.extracted_fields.use_by
                  }
                />

                <Field
                  label="Net quantity"
                  value={
                    result.extracted_fields.net_quantity
                  }
                />

                <Field
                  label="Manufacturer"
                  value={
                    result.extracted_fields
                      .manufacturer_name
                  }
                />
              </div>
            </div>

            <div className="section-card">
              <div className="section-title">
                <ShieldCheck size={19} />
                <h3>Compliance checks</h3>
              </div>

              <div className="checks">
                {result.compliance_checks.map(
                  (check) => (
                    <div
                      className="check-row"
                      key={check.rule_code}
                    >
                      <div className="check-info">
                        <strong>
                          {check.rule_name}
                        </strong>

                        <span>
                          {check.message}
                        </span>
                      </div>

                      <span
                        className={`check-status ${getStatusClass(
                          check.status
                        )}`}
                      >
                        {check.status ===
                        "MANUAL_REVIEW"
                          ? "REVIEW"
                          : check.status}
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>

            <div className="result-actions">
              <button
                className="primary-button"
                onClick={resetScan}
              >
                <Camera size={18} />
                Scan another package
              </button>
            </div>

            <div className="disclaimer">
              <AlertTriangle size={18} />

              <span>
                LEGALENS is an inspection decision-support
                system. A manual inspection may be required
                when declarations are not visible in the
                supplied image.
              </span>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div className="field">
      <span>{label}</span>

      <strong>
        {value !== null &&
        value !== undefined &&
        value !== ""
          ? value
          : "Not detected"}
      </strong>
    </div>
  );
}

export default App;