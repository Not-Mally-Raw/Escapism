# Architecture Diagram

This mermaid diagram maps the end-to-end data flow of a webhook failure event through the four core subsystems of the Orchestrator.

```mermaid
graph TD
    A[Incoming Webhook] --> B(Ingestion Gateway)
    B --> C[Inbox Table PENDING]
    C --> D(Execution Worker)
    
    subgraph Orchestrator Pipeline
        D --> E{Diagnosis Layer Track 2}
        E -- Deterministic Lookup --> F
        E -- LLM Semantic Fallback --> F
        
        F[MandateStateRecord Immutable] --> G(Guardrail Engine Track 0)
        
        G -- Computes Feasible Set --> H{Is Feasible Set > 1?}
        
        H -- No Only Escalate/Abort --> I(Decision Layer Track 3)
        H -- Yes --> J(Propensity Model Track 1)
        
        J -- P_recoverable --> I
        
        I -- Calculates EV against Cost/Multiplier --> K[Optimal Action]
    end
    
    K --> L(Razorpay API)
    K --> M(Communications / Nudge API)
    
    L --> N[Audit Log & Inbox PROCESSED]
    M --> N
    
    classDef compliance fill:#ffcccc,stroke:#ff0000,stroke-width:2px;
    classDef ai fill:#ccddff,stroke:#0033cc,stroke-width:2px;
    
    G:::compliance
    E:::ai
    J:::ai
    I:::ai
```

### Subsystem Roles
1. **Diagnosis (Track 2):** Classifies the raw bank error code and text into one of 5 canonical failure classes.
2. **Guardrails (Track 0):** Enforces hard regulatory limits (NPCI max attempts, RBI ₹15K AFA limits, 8AM-7PM contact hours).
3. **Propensity (Track 1):** Logistic Regression estimating the probability that the customer has sufficient liquidity to recover the payment.
4. **Decision (Track 3):** Combines the feasible set and the propensity score to select the action with the highest Expected Value (EV), constrained by the safety threshold `θ_digital`.
