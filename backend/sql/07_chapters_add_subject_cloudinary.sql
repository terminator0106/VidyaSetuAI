-- Add chapter metadata columns required by ingestion.
-- Safe to run multiple times.

BEGIN;

-- 1) Add columns
ALTER TABLE IF EXISTS public.chapters
  ADD COLUMN IF NOT EXISTS subject_id text,
  ADD COLUMN IF NOT EXISTS cloudinary_url text;

-- 2) Ensure FK to textbooks exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chapters_textbook_id_fkey'
  ) THEN
    ALTER TABLE public.chapters
      ADD CONSTRAINT chapters_textbook_id_fkey
      FOREIGN KEY (textbook_id)
      REFERENCES public.textbooks(id)
      ON DELETE CASCADE;
  END IF;
END $$;

-- 3) Helpful indexes
CREATE INDEX IF NOT EXISTS ix_chapters_subject_id ON public.chapters(subject_id);
CREATE INDEX IF NOT EXISTS ix_chapters_textbook_id ON public.chapters(textbook_id);

COMMIT;
