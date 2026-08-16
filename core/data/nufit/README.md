# NuFIT oscillation likelihood tables

Two-column tables (observable value, -2 log L offset) used by `table_lookup`
likelihood terms. Reference them from any model with the location-independent
`core:` prefix, e.g.

    likelihoods:
      - name: theta12_term
        kind: table_lookup
        observable: Theta12
        table_file: core:data/nufit/Normal/Theta12.csv

Record the NuFIT release these correspond to before citing results.
