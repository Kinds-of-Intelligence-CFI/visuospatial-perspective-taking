library(tidyverse); library(glmmTMB); library(car); library(emmeans)
library(kableExtra); library(gridExtra); library(grid)

# Run this script from within rotating_figure_task/results/ - all input and
# output paths are relative to that directory.


# ==========================
# LATEX TABLE FUNCTIONS
# ==========================

# Formats p-values with significance stars
fmt_p <- function(p) {
  case_when(
    p < 0.001 ~ "$<$ 0.001***",
    p < 0.01  ~ sprintf("%.3f**",  p),
    p < 0.05  ~ sprintf("%.3f*",   p),
    p < 0.1   ~ sprintf("%.3f.",   p),
    TRUE      ~ sprintf("%.3f",    p)
  )
}

# Formats p-values for EMM tables (shorter style)
fmt_p_short <- function(p) {
  case_when(
    p < 0.001 ~ "$<$.001***",
    p < 0.01  ~ sprintf("%.3f**",  p),
    p < 0.05  ~ sprintf("%.3f*",   p),
    p < 0.1   ~ sprintf("%.3f.",   p),
    TRUE      ~ sprintf("%.3f",    p)
  )
}

# Applies a named list of regex replacements to a character vector
apply_replacements <- function(x, replacements) {
  for (pattern in names(replacements)) {
    x <- str_replace_all(x, pattern, replacements[[pattern]])
  }
  x
}

# Standard term replacements shared across models
ai_term_replacements <- list(
  "\\(Intercept\\)"              = "Intercept",
  "modelgpt-4o-mini"             = "Model: GPT-4o-mini",
  "modelgpt-4o"                  = "Model: GPT-4o",
  "modelo4-mini"                 = "Model: o4-mini",
  "modelo3"                      = "Model: o3",
  "question_typespatial"         = "Question Type: Spatial",
  "angular_disparity_factor22\\.5"  = "Angular Disparity: 22.5\\\\degree",
  "angular_disparity_factor67\\.5"  = "Angular Disparity: 67.5\\\\degree",
  "angular_disparity_factor112\\.5" = "Angular Disparity: 112.5\\\\degree",
  "angular_disparity_factor157\\.5" = "Angular Disparity: 157.5\\\\degree",
  "angular_disparity_factor"     = "Angular Disparity",
  "question_type"                = "Question Type",
  "model"                        = "Model"
)

human_term_replacements <- list(
  "\\(Intercept\\)"              = "Intercept",
  "question_typespatial"         = "Question Type: Spatial",
  "angular_disparity_factor22\\.5"  = "Angular Disparity: 22.5\\\\degree",
  "angular_disparity_factor67\\.5"  = "Angular Disparity: 67.5\\\\degree",
  "angular_disparity_factor112\\.5" = "Angular Disparity: 112.5\\\\degree",
  "angular_disparity_factor157\\.5" = "Angular Disparity: 157.5\\\\degree",
  "angular_disparity_factor"     = "Angular Disparity",
  "question_type"                = "Question Type"
)

# Generates a combined coefficient + Wald test LaTeX table for a glmmTMB model
generate_model_summary_table <- function(
    model,
    caption        = "Mixed Effects Logistic Regression Model Summary",
    label          = "model_summary",
    term_replacements = NULL
) {
  if (is.null(term_replacements)) term_replacements <- ai_term_replacements

  model_summary <- summary(model)
  coef_table    <- coef(model_summary)
  # glmmTMB returns a list per component; extract the conditional model
  if (is.list(coef_table) && "cond" %in% names(coef_table)) {
    coef_table <- coef_table$cond
  }

  coef_df <- as.data.frame(coef_table) %>%
    rownames_to_column("term") %>%
    rename(estimate = Estimate, std_error = `Std. Error`,
           z_value = `z value`, p_value = `Pr(>|z|)`) %>%
    mutate(
      term      = apply_replacements(term, term_replacements),
      term      = str_replace_all(term, ":", " $\\\\times$ "),
      estimate  = sprintf("%.3f", estimate),
      std_error = sprintf("%.3f", std_error),
      z_value   = sprintf("%.3f", z_value),
      p_value   = fmt_p(p_value)
    ) %>%
    mutate(panel = "") %>%
    select(panel, term, estimate, std_error, z_value, p_value)

  wald_tests <- Anova(model, type = "III")
  wald_df <- as.data.frame(wald_tests) %>%
    rownames_to_column("term") %>%
    rename(chi_square = Chisq, df = Df, p_value = `Pr(>Chisq)`) %>%
    mutate(
      term          = apply_replacements(term, term_replacements),
      term          = str_replace_all(term, ":", " $\\\\times$ "),
      chi_square_fmt = sprintf("%.3f", chi_square),
      df_fmt         = as.character(df),
      p_value        = fmt_p(p_value)
    ) %>%
    mutate(panel = "") %>%
    select(panel, term, chi_square_fmt, df_fmt, p_value)

  combined_table <- bind_rows(
    tibble(panel = "", term = "\\textbf{A. Model Coefficients}",
           estimate = "", std_error = "", z_value = "", p_value = ""),
    coef_df,
    tibble(panel = "", term = "", estimate = "", std_error = "", z_value = "", p_value = ""),
    tibble(panel = "", term = "\\textbf{B. Type III Wald Tests}",
           estimate = "", std_error = "", z_value = "", p_value = ""),
    wald_df %>% mutate(z_value = "") %>% rename(estimate = chi_square_fmt, std_error = df_fmt)
  ) %>%
    select(-panel)

  vc <- VarCorr(model)
  if (inherits(vc, "VarCorr.glmmTMB")) {
    re_df <- data.frame(
      grp  = names(vc$cond),
      vcov = sapply(vc$cond, function(x) diag(as.matrix(x))[[1]])
    )
  } else {
    re_df <- as.data.frame(vc)
    if ("component" %in% names(re_df)) re_df <- re_df[re_df$component == "cond", ]
  }
  re_str <- paste(sprintf("%s: %.3f", re_df$grp, re_df$vcov), collapse = "; ")

  combined_table %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c("Term", "Est./($\\chi^2$)", "SE/(df)", "z", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position", "scale_down")) %>%
    add_footnote(
      c("Panel A: Coefficient estimates with Wald z-tests for individual parameters.",
        "Panel B: Type III Wald $\\chi^2$ tests for omnibus effects of factors.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1",
        sprintf("Random effect variances — %s", re_str)),
      notation = "none", escape = FALSE
    )
}

# Formats the joint_tests output into a data frame with chi_sq_fmt and p_fmt columns
fmt_joint_tests <- function(jt_obj) {
  jt_df <- as.data.frame(jt_obj)
  if ("F.ratio" %in% names(jt_df)) {
    jt_df <- jt_df %>% mutate(chi_sq = df1 * F.ratio,
                               chi_sq_fmt = sprintf("%.2f", chi_sq),
                               df_fmt = as.character(as.integer(df1)))
  } else {
    jt_df <- jt_df %>% mutate(chi_sq_fmt = sprintf("%.2f", Chisq),
                               df_fmt = as.character(as.integer(Df)))
  }
  jt_df %>% mutate(p_fmt = fmt_p_short(p.value))
}

bin_labels_display <- c("22.5" = "0--45\\degree", "67.5" = "45--90\\degree",
                         "112.5" = "90--135\\degree", "157.5" = "135--180\\degree")

rename_bin_cols <- function(df, bin_labels = bin_labels_display) {
  bin_cols <- names(df)[grepl("^bin_", names(df))]
  new_names <- sapply(bin_cols, function(x) {
    lv <- sub("bin_", "", x)
    if (lv %in% names(bin_labels)) bin_labels[lv] else lv
  })
  names(df)[grepl("^bin_", names(df))] <- new_names
  df
}

model_display_labels <- function(x) {
  case_when(
    x == "human"      ~ "Human",
    x == "gpt-4o-mini" ~ "GPT-4o-mini",
    x == "gpt-4o"     ~ "GPT-4o",
    x == "o4-mini"    ~ "o4-mini",
    x == "o3"         ~ "o3",
    TRUE              ~ as.character(x)
  )
}

# EMM table for AI models with question_type (Tests 1 and 2)
generate_ai_emm_table <- function(
    emm_object, joint_tests_object,
    caption = "Estimated Marginal Means by Angular Disparity",
    label   = "emm_summary"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(prob_fmt = sprintf("%.3f", prob))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(question_type, model, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt,
                names_prefix = "bin_") %>%
    left_join(jt_df %>% select(question_type, model, chi_sq_fmt, df_fmt, p_fmt),
              by = c("question_type", "model")) %>%
    arrange(question_type, model) %>%
    mutate(question_type = case_when(question_type == "visual"  ~ "Visual",
                                     question_type == "spatial" ~ "Spatial",
                                     TRUE ~ as.character(question_type)),
           model = model_display_labels(model)) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("question_type", "model", "chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c("Question", "Model", bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    collapse_rows(columns = 1, valign = "top", latex_hline = "none") %>%
    add_footnote(
      c("Values are estimated marginal probabilities of correct responses.",
        "Simple main effects test angular disparity within each Model $\\times$ Question Type combination.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}

# EMM table for AI Test 3 (no question_type)
generate_ai_emm_table_t3 <- function(
    emm_object, joint_tests_object,
    caption = "Estimated Marginal Means by Angular Disparity",
    label   = "emm_summary"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(prob_fmt = sprintf("%.3f", prob))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(model, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt,
                names_prefix = "bin_") %>%
    left_join(jt_df %>% select(model, chi_sq_fmt, df_fmt, p_fmt), by = "model") %>%
    arrange(model) %>%
    mutate(model = model_display_labels(model)) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("model", "chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c("Model", bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    add_footnote(
      c("Values are estimated marginal probabilities of correct responses.",
        "Simple main effects test angular disparity within each Model.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}

# EMM table for human accuracy model with question_type (Tests 1 and 2)
generate_human_emm_table <- function(
    emm_object, joint_tests_object,
    caption = "Human Estimated Marginal Means by Angular Disparity",
    label   = "human_emm_summary"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(prob_fmt = sprintf("%.3f", prob))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(question_type, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt,
                names_prefix = "bin_") %>%
    left_join(jt_df %>% select(question_type, chi_sq_fmt, df_fmt, p_fmt),
              by = "question_type") %>%
    mutate(question_type = case_when(question_type == "visual"  ~ "Visual",
                                     question_type == "spatial" ~ "Spatial",
                                     TRUE ~ as.character(question_type))) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("question_type", "chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c("Question", bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    add_footnote(
      c("Values are estimated marginal probabilities of correct responses (human participants only).",
        "Simple main effects test angular disparity within each Question Type.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}

# EMM table for human Test 3 (no question_type)
generate_human_emm_table_t3 <- function(
    emm_object, joint_tests_object,
    caption = "Human Estimated Marginal Means by Angular Disparity (Test 3)",
    label   = "human_emm_t3"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(prob_fmt = sprintf("%.3f", prob))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt,
                names_prefix = "bin_") %>%
    bind_cols(jt_df %>% select(chi_sq_fmt, df_fmt, p_fmt)) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c(bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    add_footnote(
      c("Values are estimated marginal probabilities of correct responses (human participants only).",
        "Test of angular disparity effect (visuospatial question type).",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}


# EMM table for human RT model with question_type (Tests 1 and 2)
# emmeans are on the log scale; exp(emmean) gives geometric mean RT in ms
generate_human_rt_emm_table <- function(
    emm_object, joint_tests_object,
    caption = "Human RT Estimated Marginal Means by Angular Disparity",
    label   = "human_rt_emm_summary"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(rt_fmt = sprintf("%.0f", exp(emmean)))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(question_type, angular_disparity_factor, rt_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = rt_fmt,
                names_prefix = "bin_") %>%
    left_join(jt_df %>% select(question_type, chi_sq_fmt, df_fmt, p_fmt),
              by = "question_type") %>%
    mutate(question_type = case_when(question_type == "visual"  ~ "Visual",
                                     question_type == "spatial" ~ "Spatial",
                                     TRUE ~ as.character(question_type))) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("question_type", "chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c("Question", bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    add_footnote(
      c("Values are geometric mean reaction times (ms), back-transformed from log scale.",
        "Simple main effects test angular disparity within each Question Type.",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}

# EMM table for human RT Test 3 (no question_type)
generate_human_rt_emm_table_t3 <- function(
    emm_object, joint_tests_object,
    caption = "Human RT Estimated Marginal Means by Angular Disparity (Test 3)",
    label   = "human_rt_emm_t3"
) {
  emm_df <- as.data.frame(emm_object) %>%
    mutate(rt_fmt = sprintf("%.0f", exp(emmean)))

  jt_df <- fmt_joint_tests(joint_tests_object)

  emm_wide <- emm_df %>%
    select(angular_disparity_factor, rt_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = rt_fmt,
                names_prefix = "bin_") %>%
    bind_cols(jt_df %>% select(chi_sq_fmt, df_fmt, p_fmt)) %>%
    rename_bin_cols()

  bin_cols <- names(emm_wide)[!names(emm_wide) %in% c("chi_sq_fmt", "df_fmt", "p_fmt")]

  emm_wide %>%
    kbl(format = "latex", booktabs = TRUE, caption = caption, label = label,
        col.names = c(bin_cols, "$\\chi^2$", "df", "p"),
        escape = FALSE, linesep = "") %>%
    kable_styling(latex_options = c("hold_position")) %>%
    add_footnote(
      c("Values are geometric mean reaction times (ms), back-transformed from log scale.",
        "Test of angular disparity effect (visuospatial question type).",
        "Significance codes: *** p $<$ 0.001, ** p $<$ 0.01, * p $<$ 0.05, . p $<$ 0.1"),
      notation = "none", escape = FALSE
    )
}


# ==========================
# DATA LOADING AND PREPARATION
# ==========================

df <- read_csv("vpt_task_processed.csv", show_col_types = FALSE)

df$model <- factor(df$model, levels = c("human", "gpt-4o-mini", "gpt-4o", "o4-mini", "o3"))
df$question_type <- factor(df$question_type, levels = c("visual", "spatial"))
df$stimulus_set  <- factor(df$stimulus_set,
                            levels = c("control_1","control_2","level_1","level_2","level_3"),
                            labels = c("Control 1","Control 2","Test 1","Test 2","Test 3"))
df$accuracy <- as.numeric(df$accuracy)

# Angular disparity: fold rotations > 180 back onto 0–180 scale
df$angular_disparity <- ifelse(df$rotation_forward > 180,
                                360 - df$rotation_forward,
                                df$rotation_forward)

breaks    <- seq(0, 180, by = 45)
midpoints <- head(breaks, -1) + diff(breaks) / 2

df$angular_disparity_bin <- cut(df$angular_disparity, breaks = breaks,
                                 labels = c("0-45","45-90","90-135","135-180"),
                                 include.lowest = TRUE)
df$angular_disparity_bin_numeric <- midpoints[as.numeric(df$angular_disparity_bin)]

# image_id: per-filename random effect (~3k levels per test)
df <- df %>%
  group_by(filename) %>%
  mutate(image_id = cur_group_id()) %>%
  ungroup()

cat("Unique images:", length(unique(df$image_id)), "\n")

# Sample size check
df %>%
  group_by(model, stimulus_set, question_type) %>%
  summarize(n = n(), .groups = "drop") %>%
  print(n = 50)

# AI dataset: aggregate to correct/total per (image × question_type × model)
df_ai <- df %>%
  filter(model != "human") %>%
  group_by(image_id, model, question_type, stimulus_set, angular_disparity_bin_numeric) %>%
  summarise(correct = sum(accuracy), total = n(), .groups = "drop")

# Human dataset: trial-level (participant_id present, used as random effect)
df_human <- df %>%
  filter(model == "human")

cat("AI aggregated rows:", nrow(df_ai), "\n")
cat("Human trial rows:", nrow(df_human), "\n")


# ==========================
# SECTION 1: AI MODELS
# Humans excluded; cbind(correct, total-correct) ~ model * question_type *
# angular_disparity_factor + (1|image_id)
# ==========================

run_ai_model <- function(data, formula, test_label) {
  cat(sprintf("\n=== AI Model: %s ===\n", test_label))
  m <- glmmTMB(formula, data = data, family = binomial(link = "logit"))
  print(summary(m))
  cat("\n--- Type III Wald Tests ---\n")
  print(Anova(m, type = "III"))
  m
}

# --- Test 1 ---
df_ai_t1 <- df_ai %>%
  filter(stimulus_set == "Test 1") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (AI Test 1):\n")
print(table(df_ai_t1$angular_disparity_factor))

me_ai_1 <- run_ai_model(
  df_ai_t1,
  cbind(correct, total - correct) ~ model * question_type * angular_disparity_factor + (1 | image_id),
  "Test 1"
)

emm_ai_1      <- emmeans(me_ai_1, ~ angular_disparity_factor | model * question_type, type = "response")
jt_ai_1       <- joint_tests(emm_ai_1, by = c("model", "question_type"))
cat("\n--- EMMs (AI Test 1) ---\n"); print(emm_ai_1)
cat("\n--- Simple main effects (AI Test 1) ---\n"); print(jt_ai_1)

ai1_summary_tex <- generate_model_summary_table(
  me_ai_1,
  caption = "AI Model 1 (Test 1): Angular Disparity $\\times$ Question Type $\\times$ Model",
  label   = "ai_model1_summary"
)
ai1_emm_tex <- generate_ai_emm_table(
  emm_ai_1, jt_ai_1,
  caption = "AI Model 1 (Test 1): Estimated Marginal Means by Angular Disparity",
  label   = "ai_model1_emm"
)
write_lines(ai1_summary_tex, "table_ai_model1_summary.tex")
write_lines(ai1_emm_tex,     "table_ai_model1_emm.tex")
cat("\n\n=== AI MODEL 1 SUMMARY TABLE ===\n\n"); cat(ai1_summary_tex)
cat("\n\n=== AI MODEL 1 EMM TABLE ===\n\n");     cat(ai1_emm_tex)

# --- Test 2 ---
df_ai_t2 <- df_ai %>%
  filter(stimulus_set == "Test 2") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (AI Test 2):\n")
print(table(df_ai_t2$angular_disparity_factor))

me_ai_2 <- run_ai_model(
  df_ai_t2,
  cbind(correct, total - correct) ~ model * question_type * angular_disparity_factor + (1 | image_id),
  "Test 2"
)

emm_ai_2 <- emmeans(me_ai_2, ~ angular_disparity_factor | model * question_type, type = "response")
jt_ai_2  <- joint_tests(emm_ai_2, by = c("model", "question_type"))
cat("\n--- EMMs (AI Test 2) ---\n"); print(emm_ai_2)
cat("\n--- Simple main effects (AI Test 2) ---\n"); print(jt_ai_2)

ai2_summary_tex <- generate_model_summary_table(
  me_ai_2,
  caption = "AI Model 2 (Test 2): Angular Disparity $\\times$ Question Type $\\times$ Model",
  label   = "ai_model2_summary"
)
ai2_emm_tex <- generate_ai_emm_table(
  emm_ai_2, jt_ai_2,
  caption = "AI Model 2 (Test 2): Estimated Marginal Means by Angular Disparity",
  label   = "ai_model2_emm"
)
write_lines(ai2_summary_tex, "table_ai_model2_summary.tex")
write_lines(ai2_emm_tex,     "table_ai_model2_emm.tex")
cat("\n\n=== AI MODEL 2 SUMMARY TABLE ===\n\n"); cat(ai2_summary_tex)
cat("\n\n=== AI MODEL 2 EMM TABLE ===\n\n");     cat(ai2_emm_tex)

# --- Test 3 (visual only; no question_type) ---
df_ai_t3 <- df_ai %>%
  filter(stimulus_set == "Test 3") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (AI Test 3):\n")
print(table(df_ai_t3$angular_disparity_factor))

me_ai_3 <- run_ai_model(
  df_ai_t3,
  cbind(correct, total - correct) ~ model * angular_disparity_factor + (1 | image_id),
  "Test 3"
)

emm_ai_3 <- emmeans(me_ai_3, ~ angular_disparity_factor | model, type = "response")
jt_ai_3  <- joint_tests(emm_ai_3, by = "model")
cat("\n--- EMMs (AI Test 3) ---\n"); print(emm_ai_3)
cat("\n--- Simple main effects (AI Test 3) ---\n"); print(jt_ai_3)

ai3_summary_tex <- generate_model_summary_table(
  me_ai_3,
  caption = "AI Model 3 (Test 3): Angular Disparity $\\times$ Model",
  label   = "ai_model3_summary",
  term_replacements = within(ai_term_replacements, rm("question_typespatial", "question_type"))
)
ai3_emm_tex <- generate_ai_emm_table_t3(
  emm_ai_3, jt_ai_3,
  caption = "AI Model 3 (Test 3): Estimated Marginal Means by Angular Disparity",
  label   = "ai_model3_emm"
)
write_lines(ai3_summary_tex, "table_ai_model3_summary.tex")
write_lines(ai3_emm_tex,     "table_ai_model3_emm.tex")
cat("\n\n=== AI MODEL 3 SUMMARY TABLE ===\n\n"); cat(ai3_summary_tex)
cat("\n\n=== AI MODEL 3 EMM TABLE ===\n\n");     cat(ai3_emm_tex)


# ==========================
# SECTION 2: HUMAN ACCURACY MODELS
# Trial-level; accuracy ~ question_type * angular_disparity_factor +
# (1|participant_id) + (1|image_id)
# ==========================

run_human_acc_model <- function(data, formula, test_label) {
  cat(sprintf("\n=== Human Accuracy Model: %s ===\n", test_label))
  m <- glmmTMB(formula, data = data, family = binomial(link = "logit"))
  print(summary(m))
  cat("\n--- Type III Wald Tests ---\n")
  print(Anova(m, type = "III"))
  m
}

# --- Test 1 ---
df_h_t1 <- df_human %>%
  filter(stimulus_set == "Test 1") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (Human Test 1):\n")
print(table(df_h_t1$angular_disparity_factor))

me_h_1 <- run_human_acc_model(
  df_h_t1,
  accuracy ~ question_type * angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 1"
)

emm_h_1 <- emmeans(me_h_1, ~ angular_disparity_factor | question_type, type = "response")
jt_h_1  <- joint_tests(emm_h_1, by = "question_type")
cat("\n--- EMMs (Human Test 1) ---\n"); print(emm_h_1)
cat("\n--- Simple main effects (Human Test 1) ---\n"); print(jt_h_1)

h1_summary_tex <- generate_model_summary_table(
  me_h_1,
  caption = "Human Accuracy Model 1 (Test 1): Angular Disparity $\\times$ Question Type",
  label   = "human_acc_model1_summary",
  term_replacements = human_term_replacements
)
h1_emm_tex <- generate_human_emm_table(
  emm_h_1, jt_h_1,
  caption = "Human Accuracy Model 1 (Test 1): Estimated Marginal Means by Angular Disparity",
  label   = "human_acc_model1_emm"
)
write_lines(h1_summary_tex, "table_human_acc_model1_summary.tex")
write_lines(h1_emm_tex,     "table_human_acc_model1_emm.tex")
cat("\n\n=== HUMAN ACC MODEL 1 SUMMARY TABLE ===\n\n"); cat(h1_summary_tex)
cat("\n\n=== HUMAN ACC MODEL 1 EMM TABLE ===\n\n");     cat(h1_emm_tex)

# --- Test 2 ---
df_h_t2 <- df_human %>%
  filter(stimulus_set == "Test 2") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (Human Test 2):\n")
print(table(df_h_t2$angular_disparity_factor))

me_h_2 <- run_human_acc_model(
  df_h_t2,
  accuracy ~ question_type * angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 2"
)

emm_h_2 <- emmeans(me_h_2, ~ angular_disparity_factor | question_type, type = "response")
jt_h_2  <- joint_tests(emm_h_2, by = "question_type")
cat("\n--- EMMs (Human Test 2) ---\n"); print(emm_h_2)
cat("\n--- Simple main effects (Human Test 2) ---\n"); print(jt_h_2)

h2_summary_tex <- generate_model_summary_table(
  me_h_2,
  caption = "Human Accuracy Model 2 (Test 2): Angular Disparity $\\times$ Question Type",
  label   = "human_acc_model2_summary",
  term_replacements = human_term_replacements
)
h2_emm_tex <- generate_human_emm_table(
  emm_h_2, jt_h_2,
  caption = "Human Accuracy Model 2 (Test 2): Estimated Marginal Means by Angular Disparity",
  label   = "human_acc_model2_emm"
)
write_lines(h2_summary_tex, "table_human_acc_model2_summary.tex")
write_lines(h2_emm_tex,     "table_human_acc_model2_emm.tex")
cat("\n\n=== HUMAN ACC MODEL 2 SUMMARY TABLE ===\n\n"); cat(h2_summary_tex)
cat("\n\n=== HUMAN ACC MODEL 2 EMM TABLE ===\n\n");     cat(h2_emm_tex)

# --- Test 3 (visual only; no question_type) ---
df_h_t3 <- df_human %>%
  filter(stimulus_set == "Test 3") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\nAngular disparity distribution (Human Test 3):\n")
print(table(df_h_t3$angular_disparity_factor))

me_h_3 <- run_human_acc_model(
  df_h_t3,
  accuracy ~ angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 3"
)

emm_h_3 <- emmeans(me_h_3, ~ angular_disparity_factor, type = "response")
jt_h_3  <- joint_tests(emm_h_3)
cat("\n--- EMMs (Human Test 3) ---\n"); print(emm_h_3)
cat("\n--- Joint test angular disparity (Human Test 3) ---\n"); print(jt_h_3)

h3_summary_tex <- generate_model_summary_table(
  me_h_3,
  caption = "Human Accuracy Model 3 (Test 3): Angular Disparity",
  label   = "human_acc_model3_summary",
  term_replacements = within(human_term_replacements, rm("question_typespatial", "question_type"))
)
h3_emm_tex <- generate_human_emm_table_t3(
  emm_h_3, jt_h_3,
  caption = "Human Accuracy Model 3 (Test 3): Estimated Marginal Means by Angular Disparity",
  label   = "human_acc_model3_emm"
)
write_lines(h3_summary_tex, "table_human_acc_model3_summary.tex")
write_lines(h3_emm_tex,     "table_human_acc_model3_emm.tex")
cat("\n\n=== HUMAN ACC MODEL 3 SUMMARY TABLE ===\n\n"); cat(h3_summary_tex)
cat("\n\n=== HUMAN ACC MODEL 3 EMM TABLE ===\n\n");     cat(h3_emm_tex)


# ==========================
# SECTION 3: COMBINED TABLE (AI + HUMAN)
# Reproduces paper Table 1 format with Human rows added to each test group.
# Uses already-computed EMM/joint_tests objects from sections 1 and 2.
# ==========================

fmt_p_table1 <- function(p) {
  case_when(p < 0.001 ~ "$<$.001", TRUE ~ sprintf("%.3f", p))
}

jt_to_stats_t1 <- function(jt_obj) {
  jt_df <- as.data.frame(jt_obj)
  if ("F.ratio" %in% names(jt_df)) {
    jt_df %>% mutate(chi_sq_fmt = sprintf("%.1f", df1 * F.ratio),
                     p_fmt      = fmt_p_table1(p.value))
  } else {
    jt_df %>% mutate(chi_sq_fmt = sprintf("%.1f", Chisq),
                     p_fmt      = fmt_p_table1(p.value))
  }
}

combined_ai_rows <- function(emm_obj, jt_obj, test_num) {
  emm_df <- as.data.frame(emm_obj) %>% mutate(prob_fmt = sprintf("%.2f", prob))
  jt_df  <- jt_to_stats_t1(jt_obj)
  emm_df %>%
    select(question_type, model, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt, names_prefix = "bin_") %>%
    left_join(jt_df %>% select(question_type, model, chi_sq_fmt, p_fmt),
              by = c("question_type", "model")) %>%
    mutate(model      = model_display_labels(as.character(model)),
           test_label = paste0(test_num, "-", toupper(substr(question_type, 1, 1))))
}

combined_human_rows <- function(emm_obj, jt_obj, test_num) {
  emm_df <- as.data.frame(emm_obj) %>% mutate(prob_fmt = sprintf("%.2f", prob))
  jt_df  <- jt_to_stats_t1(jt_obj)
  emm_df %>%
    select(question_type, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt, names_prefix = "bin_") %>%
    left_join(jt_df %>% select(question_type, chi_sq_fmt, p_fmt), by = "question_type") %>%
    mutate(model      = "Human",
           test_label = paste0(test_num, "-", toupper(substr(question_type, 1, 1))))
}

combined_ai_rows_t3 <- function(emm_obj, jt_obj) {
  emm_df <- as.data.frame(emm_obj) %>% mutate(prob_fmt = sprintf("%.2f", prob))
  jt_df  <- jt_to_stats_t1(jt_obj)
  emm_df %>%
    select(model, angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt, names_prefix = "bin_") %>%
    left_join(jt_df %>% select(model, chi_sq_fmt, p_fmt), by = "model") %>%
    mutate(model = model_display_labels(as.character(model)), test_label = "3-VS")
}

combined_human_rows_t3 <- function(emm_obj, jt_obj) {
  emm_df <- as.data.frame(emm_obj) %>% mutate(prob_fmt = sprintf("%.2f", prob))
  jt_df  <- jt_to_stats_t1(jt_obj)
  emm_df %>%
    select(angular_disparity_factor, prob_fmt) %>%
    pivot_wider(names_from = angular_disparity_factor, values_from = prob_fmt, names_prefix = "bin_") %>%
    bind_cols(jt_df %>% select(chi_sq_fmt, p_fmt)) %>%
    mutate(model = "Human", test_label = "3-VS")
}

combined_model_order <- c("Human", "GPT-4o-mini", "GPT-4o", "o4-mini", "o3")
combined_test_order  <- c("1-V", "1-S", "2-V", "2-S", "3-VS")

combined_tbl <- bind_rows(
  combined_human_rows(emm_h_1, jt_h_1, "1"),
  combined_ai_rows(emm_ai_1, jt_ai_1, "1"),
  combined_human_rows(emm_h_2, jt_h_2, "2"),
  combined_ai_rows(emm_ai_2, jt_ai_2, "2"),
  combined_human_rows_t3(emm_h_3, jt_h_3),
  combined_ai_rows_t3(emm_ai_3, jt_ai_3)
) %>%
  mutate(
    model      = factor(model,      levels = combined_model_order),
    test_label = factor(test_label, levels = combined_test_order)
  ) %>%
  arrange(test_label, model) %>%
  select(test_label, model, starts_with("bin_"), chi_sq_fmt, p_fmt)

combined_bin_cols <- c("0--45", "45--90", "90--135", "135--180")
names(combined_tbl)[grepl("^bin_", names(combined_tbl))] <- combined_bin_cols

combined_tex <- combined_tbl %>%
  kbl(
    format    = "latex",
    booktabs  = TRUE,
    caption   = "Angular Disparity across test conditions",
    label     = "tab:vpt_combined_emm_with_human",
    col.names = c("Test", "Model", combined_bin_cols, "$\\chi^2$", "p"),
    escape    = FALSE,
    linesep   = ""
  ) %>%
  kable_styling(latex_options = c("hold_position", "scale_down")) %>%
  collapse_rows(columns = 1, valign = "top", latex_hline = "none") %>%
  add_footnote(
    c("Values are estimated marginal probabilities of correct responses.",
      "$\\chi^2$(3) tests the simple main effect of angular disparity within each model and task.",
      "Test labels use N-T (N = 1--3; V = visual, S = spatial, VS = visuospatial)."),
    notation = "none", escape = FALSE
  )

write_lines(combined_tex, "table_vpt_combined_emm_with_human.tex")
cat("\n\n=== COMBINED EMM TABLE (AI + HUMAN) ===\n\n"); cat(combined_tex)


# ==========================
# SECTION 4: HUMAN RT MODELS
# Outcome: log(rt) with Gaussian family (identity link).
# emmeans returns log-scale means; back-transform via exp() for geometric mean ms.
# ==========================

# RT is analysed on correct trials only (error-trial RT reflects different processes),
# restricted to valid, non-zero response times.
df_human_rt <- df_human %>% filter(!is.na(rt), rt > 0, accuracy == 1)
cat("Human RT trials (correct, valid RT):", nrow(df_human_rt), "\n")
cat("Human trials excluded (missing/zero RT or incorrect):", nrow(df_human) - nrow(df_human_rt), "\n")

run_human_rt_model <- function(data, formula, test_label) {
  cat(sprintf("\n=== Human RT Model: %s ===\n", test_label))
  m <- glmmTMB(formula, data = data, family = gaussian())
  print(summary(m))
  cat("\n--- Type III Wald Tests ---\n")
  print(Anova(m, type = "III"))
  m
}

# --- Test 1 ---
df_hr_t1 <- df_human_rt %>%
  filter(stimulus_set == "Test 1") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric),
         log_rt = log(rt))

cat("\nAngular disparity distribution (Human RT Test 1):\n")
print(table(df_hr_t1$angular_disparity_factor))

me_hr_1 <- run_human_rt_model(
  df_hr_t1,
  log_rt ~ question_type * angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 1"
)

emm_hr_1 <- emmeans(me_hr_1, ~ angular_disparity_factor | question_type)
jt_hr_1  <- joint_tests(emm_hr_1, by = "question_type")
cat("\n--- EMMs (Human RT Test 1) ---\n"); print(emm_hr_1)
cat("\n--- Simple main effects (Human RT Test 1) ---\n"); print(jt_hr_1)

hr1_summary_tex <- generate_model_summary_table(
  me_hr_1,
  caption = "Human RT Model 1 (Test 1): Angular Disparity $\\times$ Question Type",
  label   = "human_rt_model1_summary",
  term_replacements = human_term_replacements
)
hr1_emm_tex <- generate_human_rt_emm_table(
  emm_hr_1, jt_hr_1,
  caption = "Human RT Model 1 (Test 1): Geometric Mean RT by Angular Disparity",
  label   = "human_rt_model1_emm"
)
write_lines(hr1_summary_tex, "table_human_rt_model1_summary.tex")
write_lines(hr1_emm_tex,     "table_human_rt_model1_emm.tex")
cat("\n\n=== HUMAN RT MODEL 1 SUMMARY TABLE ===\n\n"); cat(hr1_summary_tex)
cat("\n\n=== HUMAN RT MODEL 1 EMM TABLE ===\n\n");     cat(hr1_emm_tex)

# --- Test 2 ---
df_hr_t2 <- df_human_rt %>%
  filter(stimulus_set == "Test 2") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric),
         log_rt = log(rt))

cat("\nAngular disparity distribution (Human RT Test 2):\n")
print(table(df_hr_t2$angular_disparity_factor))

me_hr_2 <- run_human_rt_model(
  df_hr_t2,
  log_rt ~ question_type * angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 2"
)

emm_hr_2 <- emmeans(me_hr_2, ~ angular_disparity_factor | question_type)
jt_hr_2  <- joint_tests(emm_hr_2, by = "question_type")
cat("\n--- EMMs (Human RT Test 2) ---\n"); print(emm_hr_2)
cat("\n--- Simple main effects (Human RT Test 2) ---\n"); print(jt_hr_2)

hr2_summary_tex <- generate_model_summary_table(
  me_hr_2,
  caption = "Human RT Model 2 (Test 2): Angular Disparity $\\times$ Question Type",
  label   = "human_rt_model2_summary",
  term_replacements = human_term_replacements
)
hr2_emm_tex <- generate_human_rt_emm_table(
  emm_hr_2, jt_hr_2,
  caption = "Human RT Model 2 (Test 2): Geometric Mean RT by Angular Disparity",
  label   = "human_rt_model2_emm"
)
write_lines(hr2_summary_tex, "table_human_rt_model2_summary.tex")
write_lines(hr2_emm_tex,     "table_human_rt_model2_emm.tex")
cat("\n\n=== HUMAN RT MODEL 2 SUMMARY TABLE ===\n\n"); cat(hr2_summary_tex)
cat("\n\n=== HUMAN RT MODEL 2 EMM TABLE ===\n\n");     cat(hr2_emm_tex)

# --- Test 3 (visual only; no question_type) ---
df_hr_t3 <- df_human_rt %>%
  filter(stimulus_set == "Test 3") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric),
         log_rt = log(rt))

cat("\nAngular disparity distribution (Human RT Test 3):\n")
print(table(df_hr_t3$angular_disparity_factor))

me_hr_3 <- run_human_rt_model(
  df_hr_t3,
  log_rt ~ angular_disparity_factor + (1 | participant_id) + (1 | image_id),
  "Test 3"
)

emm_hr_3 <- emmeans(me_hr_3, ~ angular_disparity_factor)
jt_hr_3  <- joint_tests(emm_hr_3)
cat("\n--- EMMs (Human RT Test 3) ---\n"); print(emm_hr_3)
cat("\n--- Joint test (Human RT Test 3) ---\n"); print(jt_hr_3)

hr3_summary_tex <- generate_model_summary_table(
  me_hr_3,
  caption = "Human RT Model 3 (Test 3): Angular Disparity",
  label   = "human_rt_model3_summary",
  term_replacements = within(human_term_replacements, rm("question_typespatial", "question_type"))
)
hr3_emm_tex <- generate_human_rt_emm_table_t3(
  emm_hr_3, jt_hr_3,
  caption = "Human RT Model 3 (Test 3): Geometric Mean RT by Angular Disparity",
  label   = "human_rt_model3_emm"
)
write_lines(hr3_summary_tex, "table_human_rt_model3_summary.tex")
write_lines(hr3_emm_tex,     "table_human_rt_model3_emm.tex")
cat("\n\n=== HUMAN RT MODEL 3 SUMMARY TABLE ===\n\n"); cat(hr3_summary_tex)
cat("\n\n=== HUMAN RT MODEL 3 EMM TABLE ===\n\n");     cat(hr3_emm_tex)


# ==========================
# SECTION 5: HUMAN vs AI COMPARISON
# Aggregate both to bin-level means; descriptive table + optional plot.
# No formal joint model: comparisons are visual / noted in text.
# ==========================

# Bin-level AI means (from EMMs where available, else raw aggregation)
ai_bins <- df_ai %>%
  group_by(model, question_type, stimulus_set, angular_disparity_bin_numeric) %>%
  summarise(correct = sum(correct), total = sum(total), .groups = "drop") %>%
  mutate(prop_correct = correct / total,
         source = "AI",
         model_label = model_display_labels(as.character(model)))

# Bin-level human means
human_bins <- df_human %>%
  group_by(question_type, stimulus_set, angular_disparity_bin_numeric) %>%
  summarise(correct = sum(accuracy), total = n(), .groups = "drop") %>%
  mutate(prop_correct = correct / total,
         model = "human",
         source = "Human",
         model_label = "Human")

# Stack for Tests 1–3
comparison_df <- bind_rows(
  ai_bins    %>% filter(stimulus_set %in% c("Test 1","Test 2","Test 3")),
  human_bins %>% filter(stimulus_set %in% c("Test 1","Test 2","Test 3"))
) %>%
  mutate(
    angular_disparity_bin = case_when(
      angular_disparity_bin_numeric == 22.5  ~ "0-45",
      angular_disparity_bin_numeric == 67.5  ~ "45-90",
      angular_disparity_bin_numeric == 112.5 ~ "90-135",
      angular_disparity_bin_numeric == 157.5 ~ "135-180"
    ),
    model_label = factor(model_label,
                          levels = c("Human","GPT-4o-mini","GPT-4o","o4-mini","o3"))
  )

# Descriptive comparison table
comparison_table <- comparison_df %>%
  mutate(acc_fmt = sprintf("%.3f (%d/%d)", prop_correct, correct, total)) %>%
  select(stimulus_set, question_type, model_label, angular_disparity_bin, acc_fmt) %>%
  pivot_wider(names_from = angular_disparity_bin, values_from = acc_fmt)

cat("\n\n=== HUMAN vs AI COMPARISON TABLE ===\n\n")
print(comparison_table, n = 60)

# Comparison plot: accuracy by angular disparity bin, faceted by test × question type
comparison_plot <- comparison_df %>%
  ggplot(aes(x = angular_disparity_bin_numeric, y = prop_correct,
             colour = model_label, group = model_label,
             linetype = source, shape = source)) +
  geom_line() +
  geom_point(size = 2) +
  scale_x_continuous(breaks = c(22.5, 67.5, 112.5, 157.5),
                     labels = c("0-45", "45-90", "90-135", "135-180")) +
  scale_y_continuous(limits = c(0, 1), labels = scales::percent_format()) +
  scale_linetype_manual(values = c("AI" = "solid", "Human" = "dashed")) +
  scale_shape_manual(values = c("AI" = 16, "Human" = 17)) +
  facet_grid(question_type ~ stimulus_set) +
  labs(x = "Angular Disparity (degrees)", y = "Proportion Correct",
       colour = "Model", linetype = "Source", shape = "Source") +
  theme_bw() +
  theme(legend.position = "bottom",
        axis.text.x = element_text(angle = 45, hjust = 1))

ggsave("plot_human_vs_ai_comparison.png", comparison_plot,
       width = 12, height = 6, dpi = 300)
cat("Saved: plot_human_vs_ai_comparison.png\n")


# ==========================
# SECTION 6: FOLLOW-UP (M/W/E/3 ROTATION TASK)
# Loads vpt_follow_up.csv, computes accuracy and angular disparity,
# fits the same AI-style binomial model, and produces an EMM table.
# ==========================

df_fu_raw <- read_csv("vpt_follow_up.csv", show_col_types = FALSE)

# Clean model names and compute accuracy (case-insensitive)
df_fu <- df_fu_raw %>%
  mutate(
    model        = sub("^openai/", "", model),
    answer_norm  = tolower(trimws(model_answer)),
    target_norm  = tolower(trimws(target)),
    accuracy     = as.integer(answer_norm == target_norm),
    # Forward-facing convention: 0 = figure faces viewer
    rotation_forward = (90 - figure_rotation) %% 360,
    angular_disparity = ifelse(rotation_forward > 180,
                               360 - rotation_forward,
                               rotation_forward)
  )

breaks_fu    <- seq(0, 180, by = 45)
midpoints_fu <- head(breaks_fu, -1) + diff(breaks_fu) / 2

df_fu <- df_fu %>%
  mutate(
    angular_disparity_bin         = cut(angular_disparity, breaks = breaks_fu,
                                        labels = c("0-45","45-90","90-135","135-180"),
                                        include.lowest = TRUE),
    angular_disparity_bin_numeric = midpoints_fu[as.numeric(angular_disparity_bin)]
  )

df_fu$model <- factor(df_fu$model, levels = c("gpt-4o-mini", "gpt-4o", "o4-mini", "o3"))

# image_id random effect
df_fu <- df_fu %>%
  group_by(filename) %>%
  mutate(image_id = cur_group_id()) %>%
  ungroup()

cat("\nAngular disparity distribution (Follow-up):\n")
print(table(df_fu$angular_disparity_bin_numeric))
cat("\nSample sizes (follow-up):\n")
print(df_fu %>% group_by(model, angular_disparity_bin) %>% summarise(n = n(), .groups = "drop"), n = 20)

# Aggregate to binomial counts per (image_id, model)
df_fu_agg <- df_fu %>%
  group_by(image_id, model, angular_disparity_bin_numeric) %>%
  summarise(correct = sum(accuracy), total = n(), .groups = "drop") %>%
  mutate(angular_disparity_factor = factor(angular_disparity_bin_numeric))

cat("\n=== Follow-Up Model: M/W/E/3 Rotation Task ===\n")
me_fu <- glmmTMB(
  cbind(correct, total - correct) ~ model * angular_disparity_factor + (1 | image_id),
  data   = df_fu_agg,
  family = binomial(link = "logit")
)
print(summary(me_fu))
cat("\n--- Type III Wald Tests (Follow-Up) ---\n")
print(Anova(me_fu, type = "III"))

emm_fu <- emmeans(me_fu, ~ angular_disparity_factor | model, type = "response")
jt_fu  <- joint_tests(emm_fu, by = "model")
cat("\n--- EMMs (Follow-Up) ---\n"); print(emm_fu)
cat("\n--- Simple main effects (Follow-Up) ---\n"); print(jt_fu)

fu_summary_tex <- generate_model_summary_table(
  me_fu,
  caption = "Follow-Up Model: M/W/E/3 Rotation Task (Angular Disparity $\\times$ Model)",
  label   = "fu_model_summary",
  term_replacements = within(ai_term_replacements, rm("question_typespatial", "question_type"))
)
fu_emm_tex <- generate_ai_emm_table_t3(
  emm_fu, jt_fu,
  caption = "Follow-Up: Estimated Marginal Means by Angular Disparity (M/W/E/3)",
  label   = "fu_emm"
)
write_lines(fu_summary_tex, "table_fu_model_summary.tex")
write_lines(fu_emm_tex,     "table_fu_emm.tex")
cat("\n\n=== FOLLOW-UP MODEL SUMMARY TABLE ===\n\n"); cat(fu_summary_tex)
cat("\n\n=== FOLLOW-UP EMM TABLE ===\n\n");           cat(fu_emm_tex)


# ==========================
# SUMMARY
# ==========================

cat("\n\n========================================\n")
cat("ANALYSIS COMPLETE\n")
cat("========================================\n")
cat("\nSection 1 — AI models (Tests 1–3):\n")
cat("  table_ai_model1_summary.tex / table_ai_model1_emm.tex\n")
cat("  table_ai_model2_summary.tex / table_ai_model2_emm.tex\n")
cat("  table_ai_model3_summary.tex / table_ai_model3_emm.tex\n")
cat("\nSection 2 — Human accuracy models (Tests 1–3):\n")
cat("  table_human_acc_model1_summary.tex / table_human_acc_model1_emm.tex\n")
cat("  table_human_acc_model2_summary.tex / table_human_acc_model2_emm.tex\n")
cat("  table_human_acc_model3_summary.tex / table_human_acc_model3_emm.tex\n")
cat("\nSection 3 — Combined AI + Human table (Tests 1–3):\n")
cat("  table_vpt_combined_emm_with_human.tex\n")
cat("\nSection 4 — Human RT models (Tests 1–3):\n")
cat("  table_human_rt_model1_summary.tex / table_human_rt_model1_emm.tex\n")
cat("  table_human_rt_model2_summary.tex / table_human_rt_model2_emm.tex\n")
cat("  table_human_rt_model3_summary.tex / table_human_rt_model3_emm.tex\n")
cat("\nSection 5 — Human vs AI comparison:\n")
cat("  plot_human_vs_ai_comparison.png\n")
cat("\nSection 6 — Follow-up M/W/E/3 rotation task:\n")
cat("  table_fu_model_summary.tex / table_fu_emm.tex\n")
