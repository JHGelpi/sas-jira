-- Create table for IRIS burndown tracking
-- This table stores daily burndown metrics for IRIS initiatives

CREATE TABLE IF NOT EXISTS public.tbl_iris_burndown (
    run_date DATE NOT NULL,
    epic_key VARCHAR(50) NOT NULL,
    bug_points NUMERIC(10,2) DEFAULT 0,
    story_points NUMERIC(10,2) DEFAULT 0,
    task_research_points NUMERIC(10,2) DEFAULT 0,
    total_points NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_date, epic_key)
);

-- Create index for faster queries by epic_key
CREATE INDEX IF NOT EXISTS idx_iris_burndown_epic_key ON public.tbl_iris_burndown(epic_key);

-- Create index for faster queries by run_date
CREATE INDEX IF NOT EXISTS idx_iris_burndown_run_date ON public.tbl_iris_burndown(run_date);

-- Add comment to table
COMMENT ON TABLE public.tbl_iris_burndown IS 'Stores daily burndown metrics for IRIS initiatives including bug points, story points, and task/research points';

-- Add comments to columns
COMMENT ON COLUMN public.tbl_iris_burndown.run_date IS 'Date when the burndown snapshot was taken';
COMMENT ON COLUMN public.tbl_iris_burndown.epic_key IS 'Jira epic key (e.g., COMPDIV-123)';
COMMENT ON COLUMN public.tbl_iris_burndown.bug_points IS 'Total story points for bugs that are not done';
COMMENT ON COLUMN public.tbl_iris_burndown.story_points IS 'Total story points for stories that are not done';
COMMENT ON COLUMN public.tbl_iris_burndown.task_research_points IS 'Total story points for tasks/research that are not done';
COMMENT ON COLUMN public.tbl_iris_burndown.total_points IS 'Total of all story points (bug + story + task_research)';
COMMENT ON COLUMN public.tbl_iris_burndown.created_at IS 'Timestamp when the record was created';
