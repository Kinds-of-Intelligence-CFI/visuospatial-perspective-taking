library(tidyverse);library(lme4);library(car);library(emmeans)
library(kableExtra);library(gridExtra);library(grid)

# Run this script from within director_task/results/ - all input and output
# paths are relative to that directory.

# ==========================
# LATEX TABLE FUNCTIONS
# ==========================

#' Generate combined model summary table (coefficients + Wald tests)
#'
#' @param model A fitted glmer model object
#' @param caption Character string for table caption
#' @param label Character string for table label
#' @param term_replacements Named list of term replacements for formatting
#' @return A kableExtra LaTeX table object
generate_model_summary_table <- function(
    model, 
    caption = "Mixed Effects Logistic Regression Model Summary",
    label = "model_summary",
    term_replacements = NULL
) {
  
  # Default term replacements if none provided
  if (is.null(term_replacements)) {
    term_replacements <- list(
      "\\(Intercept\\)" = "Intercept",
      "modelgpt-4o-mini" = "Model: GPT-4o-mini",
      "modelgpt-4o" = "Model: GPT-4o",
      "modelo4-mini" = "Model: o4-mini",
      "modelo3" = "Model: o3",
      "formatimage" = "Format: Image",
      "visual_perspectivevisual-different" = "Visual PT: Different",
      "relative_adjectivesize" = "Rel. Adj: Size",
      "relative_adjectivespatial" = "Rel. Adj: Spatial",
      "spatial_adjectivevertical" = "Spatial PT: Shared",
      "spatial_adjectivehorizontal" = "Spatial PT: Different",
      "perspective_reversalreversed" = "Persp. Reversal: Director POV",
      "model" = "Model",
      "format" = "Format",
      "visual_perspective" = "Visual PT",
      "relative_adjective" = "Rel. Adj",
      "spatial_adjective" = "Spatial PT",
      "perspective_reversal" = "Persp. Reversal"
    )
  }
  
  # Extract model summary
  model_summary <- summary(model)
  coef_table <- coef(model_summary)
  
  # Create coefficient table
  coef_df <- as.data.frame(coef_table) %>%
    rownames_to_column("term") %>%
    rename(
      estimate = Estimate,
      std_error = `Std. Error`,
      z_value = `z value`,
      p_value = `Pr(>|z|)`
    ) %>%
    mutate(
      estimate = sprintf("%.3f", estimate),
      std_error = sprintf("%.3f", std_error),
      z_value = sprintf("%.3f", z_value),
      p_value = case_when(
        p_value < 0.001 ~ "$<$ 0.001***",
        p_value < 0.01 ~ sprintf("%.3f**", p_value),
        p_value < 0.05 ~ sprintf("%.3f*", p_value),
        p_value < 0.1 ~ sprintf("%.3f.", p_value),
        TRUE ~ sprintf("%.3f", p_value)
      )
    )
  
  # Apply term replacements
  for (pattern in names(term_replacements)) {
    coef_df$term <- str_replace_all(coef_df$term, pattern, term_replacements[[pattern]])
  }
  
  # Replace interaction colons with times AFTER other substitutions
  coef_df <- coef_df %>%
    mutate(term = str_replace_all(term, "(?<!Model|Format|Visual PT|Rel\\. Adj|Spatial PT|Persp\\. Reversal):", " $\\\\times$ "))
  
  coef_df <- coef_df %>%
    mutate(panel = "") %>%
    select(panel, term, estimate, std_error, z_value, p_value)
  
  # Create Wald tests table
  wald_tests <- Anova(model, type = "III")
  wald_df <- as.data.frame(wald_tests) %>%
    rownames_to_column("term") %>%
    rename(
      chi_square = Chisq,
      df = Df,
      p_value = `Pr(>Chisq)`
    ) %>%
    mutate(
      chi_square_fmt = sprintf("%.3f", chi_square),
      df_fmt = as.character(df),
      p_value = case_when(
        p_value < 0.001 ~ "$<$ 0.001***",
        p_value < 0.01 ~ sprintf("%.3f**", p_value),
        p_value < 0.05 ~ sprintf("%.3f*", p_value),
        p_value < 0.1 ~ sprintf("%.3f.", p_value),
        TRUE ~ sprintf("%.3f", p_value)
      )
    )
  
  # Apply term replacements to Wald tests
  for (pattern in names(term_replacements)) {
    wald_df$term <- str_replace_all(wald_df$term, pattern, term_replacements[[pattern]])
  }
  
  wald_df <- wald_df %>%
    mutate(term = str_replace_all(term, ":", " $\\\\times$ ")) %>%
    mutate(panel = "") %>%
    select(panel, term, chi_square_fmt, df_fmt, p_value)
  
  # Combine with panel headers and spacer rows
  combined_table <- bind_rows(
    tibble(panel = "", term = "\\textbf{A. Model Coefficients}", estimate = "", std_error = "", z_value = "", p_value = ""),
    coef_df,
    tibble(panel = "", term = "", estimate = "", std_error = "", z_value = "", p_value = ""),
    tibble(panel = "", term = "\\textbf{B. Type III Wald Tests}", estimate = "", std_error = "", z_value = "", p_value = ""),
    wald_df %>% 
      mutate(z_value = "") %>%
      rename(estimate = chi_square_fmt, std_error = df_fmt)
  ) %>%
    select(-panel)
  
  # Create combined LaTeX table
  combined_latex <- combined_table %>%
    kbl(format = "latex", 
        booktabs = TRUE,
        caption = caption,
        label = label,
        col.names = c("Term", "Est./($\\chi^2$)", "SE/(df)", "z", "p"),
        escape = FALSE,
        linesep = "") %>%
    kable_styling(latex_options = c("hold_position", "scale_down")) %>%
    add_footnote(
      c("Panel A: Coefficient estimates with Wald z-tests for individual parameters",
        "Panel B: Type III Wald $\\chi^2$ tests for omnibus effects of factors",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1",
        sprintf("Random effect variance (trial ID): %.3f", as.data.frame(VarCorr(model))$vcov[1])),
      notation = "none",
      escape = FALSE
    )
  
  return(combined_latex)
}


#' Generate pairwise comparisons table with estimated marginal means
#'
#' @param model A fitted glmer model object
#' @param contrast_specs List of contrast specifications, each containing:
#'   - formula: emmeans formula (e.g., "visual_perspective | format")
#'   - comparison_label: Label for the comparison (e.g., "Shared vs. Different")
#'   - level1_name: Name for first level (e.g., "Shared")
#'   - level2_name: Name for second level (e.g., "Different")
#'   - panel_label: Panel label (e.g., "A. Perspective within Format")
#'   - nested_context: Optional second grouping variable for nested contexts
#'   - filter_context: Optional named list to filter results (e.g., list(model = "gpt-4o"))
#'   - context_labels: Optional named list to replace context labels (e.g., list("vertical" = "Vertical", "none" = "No adjective"))
#' @param caption Character string for table caption
#' @param label Character string for table label
#' @return A kableExtra LaTeX table object
generate_pairwise_table <- function(
    model,
    contrast_specs,
    caption = "Pairwise Comparisons with Estimated Marginal Means",
    label = "pairwise_comparisons"
) {
  
  # Helper function to format contrasts
  format_contrasts_with_emms <- function(df, level1_name, level2_name, nested_context = NULL, context_labels = NULL) {
    result <- df %>%
      mutate(
        group = str_replace_all(group, "_", "-"),
        level1_label = level1_name,
        level2_label = level2_name,
        est = if("estimate" %in% names(.)) sprintf("%.3f", estimate) else sprintf("%.3f", odds.ratio),
        se = sprintf("%.3f", SE),
        z_val = sprintf("%.3f", z.ratio),
        p.value = case_when(
          p.value < 0.001 ~ "$<$ 0.001***",
          p.value < 0.01 ~ sprintf("%.3f**", p.value),
          p.value < 0.05 ~ sprintf("%.3f*", p.value),
          p.value < 0.1 ~ sprintf("%.3f.", p.value),
          TRUE ~ sprintf("%.3f", p.value)
        )
      )
    
    # Apply custom context labels if provided
    if (!is.null(context_labels)) {
      for (old_label in names(context_labels)) {
        result <- result %>%
          mutate(group = str_replace_all(group, fixed(old_label), context_labels[[old_label]]))
      }
    }
    
    # If nested context exists, combine with main group
    if (!is.null(nested_context) && nested_context %in% names(df)) {
      result <- result %>%
        mutate(group = paste0(.data[[nested_context]], ": ", group))
    }
    
    result %>%
      select(comparison, group, level1_label, level2_label, prob_level1, prob_level2, est, se, z_val, p.value)
  }
  
  # Process each contrast specification
  all_contrasts <- list()
  
  for (i in seq_along(contrast_specs)) {
    spec <- contrast_specs[[i]]
    
    # Parse the formula string to extract variables and conditioning
    formula_parts <- str_split(spec$formula, "\\s*\\|\\s*")[[1]]
    main_var <- str_trim(formula_parts[1])
    cond_vars_str <- if(length(formula_parts) > 1) str_trim(formula_parts[2]) else NULL
    
    # Parse multiple conditioning variables (separated by *)
    cond_vars <- if (!is.null(cond_vars_str)) {
      str_split(cond_vars_str, "\\s*\\*\\s*")[[1]] %>% str_trim()
    } else {
      NULL
    }
    
    # Add nested_context to conditioning variables if specified
    if (!is.null(spec$nested_context) && !is.null(spec$filter_context)) {
      if (is.null(cond_vars)) {
        cond_vars <- spec$nested_context
      } else if (!(spec$nested_context %in% cond_vars)) {
        cond_vars <- c(cond_vars, spec$nested_context)
      }
    }
    
    # Build emmeans formula
    if (!is.null(cond_vars)) {
      cond_formula <- paste(cond_vars, collapse = " * ")
      emm_formula <- as.formula(paste0("pairwise ~ ", main_var, " | ", cond_formula))
    } else {
      emm_formula <- as.formula(paste0("pairwise ~ ", main_var))
    }
    
    # Calculate emmeans
    contrast_result <- emmeans(model, emm_formula, type = "response", adjust = "bonferroni")
    
    # Extract contrasts
    df_contrasts <- as.data.frame(contrast_result$contrasts)
    
    # Extract emmeans probabilities
    emm_probs <- as.data.frame(contrast_result$emmeans) %>%
      rename(probability = prob) %>%
      mutate(probability = sprintf("%.3f", probability))
    
    # Apply filter if specified
    if (!is.null(spec$filter_context)) {
      for (filter_var in names(spec$filter_context)) {
        filter_value <- spec$filter_context[[filter_var]]
        df_contrasts <- df_contrasts %>%
          filter(.data[[filter_var]] == filter_value)
        emm_probs <- emm_probs %>%
          filter(.data[[filter_var]] == filter_value)
      }
    }
    
    # Determine which variable is being contrasted
    contrast_var <- main_var
    
    # Get unique levels of the contrast variable
    levels_contrast <- unique(emm_probs[[contrast_var]])
    
    if (!is.null(cond_vars)) {
      # Get primary grouping variable (first from original formula, not including nested_context used for filtering)
      original_cond_vars <- if (!is.null(cond_vars_str)) {
        str_split(cond_vars_str, "\\s*\\*\\s*")[[1]] %>% str_trim()
      } else {
        NULL
      }
      
      primary_group <- if (!is.null(original_cond_vars)) original_cond_vars[1] else cond_vars[1]
      
      # Create group column based on primary grouping variable
      df_contrasts <- df_contrasts %>%
        mutate(
          comparison = spec$comparison_label,
          group = as.character(.data[[primary_group]])
        )
      
      # Join probabilities - need to join on ALL conditioning variables
      join_vars <- cond_vars
      
      df_contrasts <- df_contrasts %>%
        left_join(
          emm_probs %>% 
            filter(.data[[contrast_var]] == levels_contrast[1]) %>%
            select(all_of(join_vars), prob_level1 = probability),
          by = join_vars
        ) %>%
        left_join(
          emm_probs %>% 
            filter(.data[[contrast_var]] == levels_contrast[2]) %>%
            select(all_of(join_vars), prob_level2 = probability),
          by = join_vars
        )
    } else {
      # No grouping variable - simple contrast
      df_contrasts <- df_contrasts %>%
        mutate(
          comparison = spec$comparison_label,
          group = "",
          prob_level1 = emm_probs$probability[emm_probs[[contrast_var]] == levels_contrast[1]][1],
          prob_level2 = emm_probs$probability[emm_probs[[contrast_var]] == levels_contrast[2]][1]
        )
    }
    
    # Don't add nested context to display if we're filtering by it (since it's in the panel label)
    nested_display <- if (!is.null(spec$nested_context) && !is.null(spec$filter_context) && 
                          spec$nested_context %in% names(spec$filter_context)) {
      NULL
    } else if (!is.null(spec$nested_context)) {
      spec$nested_context
    } else if (!is.null(cond_vars) && length(cond_vars) > 1) {
      cond_vars[2]
    } else {
      NULL
    }
    
    # Add panel header
    all_contrasts[[i]] <- list(
      header = tibble(
        comparison = paste0("\\textbf{", spec$panel_label, "}"),
        group = "", 
        level1_label = "", level2_label = "", prob_level1 = "", prob_level2 = "",
        est = "", se = "", z_val = "", p.value = ""
      ),
      data = format_contrasts_with_emms(df_contrasts, spec$level1_name, spec$level2_name, nested_display, spec$context_labels),
      spacer = tibble(
        comparison = "", group = "", 
        level1_label = "", level2_label = "", prob_level1 = "", prob_level2 = "",
        est = "", se = "", z_val = "", p.value = ""
      )
    )
  }
  
  # Combine all sections
  pairwise_combined_df <- bind_rows(
    lapply(all_contrasts, function(x) bind_rows(x$header, x$data, x$spacer)) %>%
      bind_rows()
  )
  
  # Generate LaTeX with dynamic column headers
  pairwise_latex <- pairwise_combined_df %>%
    mutate(
      level1_display = ifelse(level1_label == "" | level1_label == " ", "", 
                              paste0(level1_label, ": ", prob_level1)),
      level2_display = ifelse(level2_label == "" | level2_label == " ", "", 
                              paste0(level2_label, ": ", prob_level2))
    ) %>%
    select(comparison, group, level1_display, level2_display, est, se, z_val, p.value) %>%
    kbl(format = "latex", 
        booktabs = TRUE,
        caption = caption,
        label = label,
        col.names = c("Contrast", "Context", "Level 1", "Level 2", "Estimate", "SE", "z", "p"),
        escape = FALSE,
        linesep = "") %>%
    kable_styling(latex_options = c("hold_position", "scale_down")) %>%
    add_footnote(
      c("Level 1 and Level 2 columns show condition labels with probability estimates.",
        "Estimate is the difference on the logit (log-odds) scale.",
        "P-values adjusted using the Bonferroni method within each family of comparisons.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none",
      escape = FALSE
    )
  
  return(pairwise_latex)
}

# ==========================
# VPT Director Task Analysis
# ==========================

df <- read_csv("director_task_processed.csv")

# Refuse stale/duplicated inputs before fitting models or overwriting tables.
trial_key <- c("dataset_path", "image_path", "model", "ascii_image")
stopifnot(!anyDuplicated(df[trial_key]))
stopifnot(!any(df$task_name == "control_task", na.rm = TRUE))
stopifnot(!any(grepl("inventory management system", df$block_description, fixed = TRUE)))
df$format <- factor(df$format, levels = c('ascii','image'))
df$model <- factor(df$model, levels = c('gpt-4o-mini','gpt-4o','o4-mini','o3'))
df$visual_perspective <- factor(df$visual_perspective, levels = c('visual-shared','visual-different'))
df$relative_adjective <- factor(df$relative_adjective, levels = c('none','size','spatial'))
df$spatial_adjective <- factor(df$spatial_adjective, levels = c('none','vertical','horizontal'))
df$perspective_reversal <- factor(df$perspective_reversal, levels = c('not_reversed','reversed'))
df$accuracy <- as.numeric(df$accuracy)

# create trial_id
sample_size_check <- df %>% 
  group_by(model, format, visual_perspective) %>% 
  summarize(n = n(), .groups = "drop")
print(sample_size_check)

df <- df %>%
  group_by(format, visual_perspective, relative_adjective, 
           spatial_adjective, perspective_reversal) %>%
  mutate(trial_id = cur_group_id()) %>%
  ungroup()
cat("Number of unique trials:", length(unique(df$trial_id)), "\n")

# aggregate data
df_agg <- df %>%
  group_by(trial_id, model, format, visual_perspective, 
           relative_adjective, spatial_adjective, perspective_reversal) %>%
  summarise(
    correct = sum(accuracy),
    total = n(),
    .groups = "drop"
  )

# --------------------------------------
# 1. model x format x visual perspective
# --------------------------------------

spatial_shared_df <- df_agg[df_agg$spatial_adjective != "horizontal", ]
spatial_shared_df <- spatial_shared_df[spatial_shared_df$perspective_reversal == "reversed", ]

me_1 <- glmer(
  cbind(correct, total - correct) ~ model * format * visual_perspective  + 
    (1 | trial_id),  
  data = spatial_shared_df, 
  family = binomial(link = "logit"),
  control = glmerControl(
    optimizer = "bobyqa",
    optCtrl = list(maxfun = 2e5)
  )
)

cat("\n=== Model 1 Summary ===\n")
print(summary(me_1))
cat("\n=== Type III Wald Tests ===\n")
print(Anova(me_1, type = "III"))
cat("\n=== Format means ===\n")
emmeans(me_1, ~ format, type = "response")
cat("\n=== VPT means ===\n")
emmeans(me_1, ~ visual_perspective, type = "response")

# Generate tables for Model 1
model1_summary_table <- generate_model_summary_table(
  model = me_1,
  caption = "Model 1: Format × Visual PT × Model",
  label = "model1_summary"
)

model1_pairwise_table <- generate_pairwise_table(
  model = me_1,
  contrast_specs = list(
    list(
      formula = "visual_perspective | format",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(A. Perspective $\times$ Format)",
      context_labels = list("image" = "Image", "ascii" = "ASCII")
    ),
    list(
      formula = "format | visual_perspective",
      comparison_label = "ASCII vs. Image",
      level1_name = "ASCII",
      level2_name = "Image",
      panel_label = r"(B. Format $\times$ Perspective)",
      context_labels = list("visual-shared" = "Visual-shared", "visual-different" = "Visual-different")
    ),
    list(
      formula = "visual_perspective | model",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(C. Perspective $\times$ Model)"
    ),
    list(
      formula = "format | model",
      comparison_label = "ASCII vs. Image",
      level1_name = "ASCII",
      level2_name = "Image",
      panel_label = r"(D. Format $\times$ Model)"
    )
  ),
  caption = "Model 1: Pairwise Comparisons",
  label = "model1_pairwise"
)

cat("\n\n=== MODEL 1 SUMMARY TABLE ===\n\n")
cat(model1_summary_table)
cat("\n\n=== MODEL 1 PAIRWISE TABLE ===\n\n")
cat(model1_pairwise_table)

write_lines(model1_summary_table, "table_model1_summary.tex")
write_lines(model1_pairwise_table, "table_model1_pairwise.tex")


# --------------------------------------
# 2. model x relative adjective x visual perspective
# --------------------------------------

me_2 <- glmer(
  cbind(correct, total - correct) ~ model * relative_adjective * visual_perspective  + 
    format + 
    (1 | trial_id),  
  data = spatial_shared_df, 
  family = binomial(link = "logit"),
  control = glmerControl(
    optimizer = "bobyqa",
    optCtrl = list(maxfun = 2e5)
  )
)

cat("\n=== Model 2 Summary ===\n")
print(summary(me_2))
cat("\n=== Type III Wald Tests ===\n")
print(Anova(me_2, type = "III"))
cat("\n=== relative adjective means ===\n")
emmeans(me_2, ~ relative_adjective, type = "response")

emm_ra_vp <- emmeans(
  me_2,
  ~ visual_perspective | relative_adjective,
  type = "response"
)
pairs(emm_ra_vp, adjust = "Bonferroni")

# Generate tables for Model 2
model2_summary_table <- generate_model_summary_table(
  model = me_2,
  caption = "Model 2: Relative Adjective × Visual Perspective × Model",
  label = "model2_summary"
)

model2_pairwise_table <- generate_pairwise_table(
  model = me_2,
  contrast_specs = list(
    list(
      formula = "visual_perspective | relative_adjective",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "A. GPT-4o-mini",
      nested_context = "model",
      filter_context = list(model = "gpt-4o-mini"),
      context_labels = list("none" = "None", "size" = "Size", "spatial" = "Spatial")
    ),
    list(
      formula = "visual_perspective | relative_adjective",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "B. GPT-4o",
      nested_context = "model",
      filter_context = list(model = "gpt-4o"),
      context_labels = list("none" = "None", "size" = "Size", "spatial" = "Spatial")
    ),
    list(
      formula = "visual_perspective | relative_adjective",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "C. o4-mini",
      nested_context = "model",
      filter_context = list(model = "o4-mini"),
      context_labels = list("none" = "None", "size" = "Size", "spatial" = "Spatial")
    ),
    list(
      formula = "visual_perspective | relative_adjective",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "D. o3",
      nested_context = "model",
      filter_context = list(model = "o3"),
      context_labels = list("none" = "None", "size" = "Size", "spatial" = "Spatial")
    )
  ),
  caption = "Model 2: Pairwise Comparisons",
  label = "model2_pairwise"
)

cat("\n\n=== MODEL 2 SUMMARY TABLE ===\n\n")
cat(model2_summary_table)
cat("\n\n=== MODEL 2 PAIRWISE TABLE ===\n\n")
cat(model2_pairwise_table)

write_lines(model2_summary_table, "table_model2_summary.tex")
write_lines(model2_pairwise_table, "table_model2_pairwise.tex")


# --------------------------------------
# 3. model x spatial perspective x perspective reversal
# --------------------------------------

spatial_df <- df_agg[df_agg$relative_adjective == "spatial", ]
spatial_df <- spatial_df[spatial_df$visual_perspective == "visual-shared", ]

me_3 <- glmer(
  cbind(correct, total - correct) ~ model * spatial_adjective * perspective_reversal  + 
    format + 
    (1 | trial_id),  
  data = spatial_df, 
  family = binomial(link = "logit"),
  control = glmerControl(
    optimizer = "bobyqa",
    optCtrl = list(maxfun = 2e5)
  )
)

cat("\n=== Model 3 Summary ===\n")
print(summary(me_3))
cat("\n=== Type III Wald Tests ===\n")
print(Anova(me_3, type = "III"))
cat("\n=== Pairwise comparisons ===\n")
emm_sp_pr <- emmeans(
  me_3,
  ~ spatial_adjective | perspective_reversal,
  type = "response"
)
emm_sp_pr
pairs(emm_sp_pr, adjust = "Bonferroni")

# Generate tables for Model 3
model3_summary_table <- generate_model_summary_table(
  model = me_3,
  caption = "Model 3: Spatial Perspective × Perspective Reversal × Model",
  label = "model3_summary"
)

model3_pairwise_table <- generate_pairwise_table(
  model = me_3,
  contrast_specs = list(
    list(
      formula = "spatial_adjective | perspective_reversal",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "A. GPT-4o-mini",
      nested_context = "model",
      filter_context = list(model = "gpt-4o-mini"),
      context_labels = list("not-reversed" = "Participant POV", "reversed" = "Director POV")
    ),
    list(
      formula = "spatial_adjective | perspective_reversal",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "B. GPT-4o",
      nested_context = "model",
      filter_context = list(model = "gpt-4o"),
      context_labels = list("not-reversed" = "Participant POV", "reversed" = "Director POV")
    ),
    list(
      formula = "spatial_adjective | perspective_reversal",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "C. o4-mini",
      nested_context = "model",
      filter_context = list(model = "o4-mini"),
      context_labels = list("not-reversed" = "Participant POV", "reversed" = "Director POV")
    ),
    list(
      formula = "spatial_adjective | perspective_reversal",
      comparison_label = "Shared vs. Different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = "D. o3",
      nested_context = "model",
      filter_context = list(model = "o3"),
      context_labels = list("not-reversed" = "Participant POV", "reversed" = "Director POV")
    )
  ),
  caption = "Model 3: Pairwise Comparisons",
  label = "model3_pairwise"
)

cat("\n\n=== MODEL 3 SUMMARY TABLE ===\n\n")
cat(model3_summary_table)
cat("\n\n=== MODEL 3 PAIRWISE TABLE ===\n\n")
cat(model3_pairwise_table)

write_lines(model3_summary_table, "table_model3_summary.tex")
write_lines(model3_pairwise_table, "table_model3_pairwise.tex")


# --------------------------------------
# 4. model x spatial perspective x visual perspective
# --------------------------------------

vs_df <- df_agg[df_agg$relative_adjective == "spatial", ]
vs_df <- vs_df[vs_df$perspective_reversal == "reversed", ]

me_4 <- glmer(
  cbind(correct, total - correct) ~ model * visual_perspective * spatial_adjective  + 
    format + 
    (1 | trial_id),  
  data = vs_df, 
  family = binomial(link = "logit"),
  control = glmerControl(
    optimizer = "bobyqa",
    optCtrl = list(maxfun = 2e5)
  )
)

cat("\n=== Model 4 Summary ===\n")
print(summary(me_4))
cat("\n=== Type III Wald Tests ===\n")
print(Anova(me_4, type = "III"))

# Generate tables for Model 4
model4_summary_table <- generate_model_summary_table(
  model = me_4,
  caption = "Model 4: Visual Perspective × Spatial Perspective × Model",
  label = "model4_summary"
)

model4_pairwise_table <- generate_pairwise_table(
  model = me_4,
  contrast_specs = list(
    list(
      formula = "visual_perspective | spatial_adjective",
      comparison_label = "Visual-shared vs. Visual-different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(A. Visual $\times$ Spatial)",
      context_labels = list("vertical" = "Spatial-shared", "horizontal" = "Spatial-different")
    ),
    list(
      formula = "spatial_adjective | visual_perspective",
      comparison_label = "Spatial-shared vs. Spatial-different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(B. Spatial $\times$ Visual)",
      context_labels = list("visual-shared" = "Visual-shared", "visual-different" = "Visual-different")
    ),
    list(
      formula = "visual_perspective | model",
      comparison_label = "Visual-shared vs. Visual-different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(C. Visual $\times$ Model)",
      context_labels = list("visual-shared" = "Visual-shared", "visual-different" = "Visual-different")
    ),
    list(
      formula = "spatial_adjective | model",
      comparison_label = "Spatial-shared vs. Spatial-different",
      level1_name = "Shared",
      level2_name = "Different",
      panel_label = r"(D. Spatial $\times$ Model)",
      context_labels = list("vertical" = "Spatial-shared", "horizontal" = "Spatial-different")
    )
  ),
  caption = "Model 4: Pairwise Comparisons Including Double Demand Effects",
  label = "model4_pairwise_extended"
)
 

cat("\n\n=== MODEL 4 SUMMARY TABLE ===\n\n")
cat(model4_summary_table)
cat("\n\n=== MODEL 4 PAIRWISE TABLE ===\n\n")
cat(model4_pairwise_table)

write_lines(model4_summary_table, "table_model4_summary.tex")
write_lines(model4_pairwise_table, "table_model4_pairwise.tex")

# --------------------------------------
# Model 4: Compact EMM Summary Table (Visual and Spatial perspective by Model)
# --------------------------------------

# Get EMMs and contrasts for visual perspective by model
emm_visual <- emmeans(me_4, ~ visual_perspective | model, type = "response")
contrasts_visual <- pairs(emm_visual, adjust = "none")
contrasts_visual_df <- as.data.frame(contrasts_visual)
emm_visual_df <- as.data.frame(emm_visual)

# Get EMMs and contrasts for spatial perspective by model
emm_spatial <- emmeans(me_4, ~ spatial_adjective | model, type = "response")
contrasts_spatial <- pairs(emm_spatial, adjust = "none")
contrasts_spatial_df <- as.data.frame(contrasts_spatial)
emm_spatial_df <- as.data.frame(emm_spatial)

# Build visual perspective rows
visual_rows <- data.frame(
  type = "Visual",
  model = levels(factor(emm_visual_df$model)),
  shared = emm_visual_df$prob[emm_visual_df$visual_perspective == "visual-shared"],
  different = emm_visual_df$prob[emm_visual_df$visual_perspective == "visual-different"],
  estimate = contrasts_visual_df$odds.ratio,
  se = contrasts_visual_df$SE,
  p = contrasts_visual_df$p.value
)

# Build spatial perspective rows
spatial_rows <- data.frame(
  type = "Spatial",
  model = levels(factor(emm_spatial_df$model)),
  shared = emm_spatial_df$prob[emm_spatial_df$spatial_adjective == "vertical"],
  different = emm_spatial_df$prob[emm_spatial_df$spatial_adjective == "horizontal"],
  estimate = contrasts_spatial_df$odds.ratio,
  se = contrasts_spatial_df$SE,
  p = contrasts_spatial_df$p.value
)

# Combine
model4_emm_summary <- bind_rows(visual_rows, spatial_rows)

# Format for display
model4_emm_summary <- model4_emm_summary %>%
  mutate(
    model = case_when(
      model == "gpt-4o-mini" ~ "GPT-4o-mini",
      model == "gpt-4o" ~ "GPT-4o",
      model == "o4-mini" ~ "o4-mini",
      model == "o3" ~ "o3",
      TRUE ~ as.character(model)
    ),
    model = factor(model, levels = c("GPT-4o-mini", "GPT-4o", "o4-mini", "o3")),
    type = factor(type, levels = c("Visual", "Spatial")),
    shared_fmt = sprintf("%.2f", shared),
    different_fmt = sprintf("%.2f", different),
    estimate_fmt = sprintf("%.2f", estimate),
    se_fmt = sprintf("%.2f", se),
    p_fmt = case_when(
      p < 0.001 ~ "$<$.001",
      TRUE ~ sprintf("%.3f", p)
    )
  ) %>%
  arrange(type, model) %>%
  select(type, model, shared_fmt, different_fmt, estimate_fmt, se_fmt, p_fmt)

# Create LaTeX table
col_names <- c("Type", "Model", "Shared", "Different", "OR", "SE", "p")

model4_emm_latex <- model4_emm_summary %>%
  kbl(format = "latex",
      booktabs = TRUE,
      caption = "Model 4: Estimated Marginal Means for Visual and Spatial Perspective by Model",
      label = "model4_emm_summary",
      col.names = col_names,
      escape = FALSE,
      linesep = "") %>%
  kable_styling(latex_options = c("hold_position")) %>%
  collapse_rows(columns = 1, valign = "top", latex_hline = "none") %>%
  footnote(
    general = "OR and SE from pairwise contrast (Shared vs Different).",
    general_title = "",
    threeparttable = TRUE,
    escape = FALSE
  )

cat("\n\n=== MODEL 4 EMM SUMMARY TABLE ===\n\n")
cat(model4_emm_latex)

write_lines(model4_emm_latex, "table_model4_emm_summary.tex")
