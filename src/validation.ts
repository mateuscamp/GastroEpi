import { z } from "zod";

export function validarCPF(cpf: string): boolean {
  const clean = cpf.replace(/\D/g, "");
  if (clean.length !== 11) return false;
  if (/^(\d)\1{10}$/.test(clean)) return false;

  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += parseInt(clean.charAt(i)) * (10 - i);
  }
  let rev = 11 - (sum % 11);
  if (rev === 10 || rev === 11) rev = 0;
  if (rev !== parseInt(clean.charAt(9))) return false;

  sum = 0;
  for (let i = 0; i < 10; i++) {
    sum += parseInt(clean.charAt(i)) * (11 - i);
  }
  rev = 11 - (sum % 11);
  if (rev === 10 || rev === 11) rev = 0;
  if (rev !== parseInt(clean.charAt(10))) return false;

  return true;
}

export function formatarCPF(cpf: string): string {
  const clean = cpf.replace(/\D/g, "");
  if (clean.length !== 11) return clean;
  return `${clean.substring(0, 3)}.${clean.substring(3, 6)}.${clean.substring(6, 9)}-${clean.substring(9)}`;
}

export function converterParaISO(dataBr: string): string {
  const parts = dataBr.split("/");
  if (parts.length !== 3) return "";
  const [dia, mes, ano] = parts;
  return `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`;
}

export function converterParaBR(dataIso: string): string {
  if (!dataIso) return "";
  const parts = dataIso.split("-");
  if (parts.length !== 3) return "";
  const [ano, mes, dia] = parts;
  return `${dia}/${mes}/${ano}`;
}

export const historicoFamiliarSchema = z.object({
  id: z.number().optional().nullable(),
  parentesco: z.string().min(1, "Parentesco é obrigatório"),
  grau: z.coerce.number().int().min(1).max(3, "Grau de parentesco deve ser de 1 a 3"),
  idade_diagnostico: z.preprocess(
    (val) => (val === "" || val === null || val === undefined ? null : Number(val)),
    z.number().int().min(0, "Idade deve ser maior ou igual a 0").nullable()
  ),
});

export const pacienteSchema = z.object({
  id: z.number().optional().nullable(),
  numero_prontuario: z.string().min(1, "Prontuário é obrigatório"),
  cpf: z.preprocess(
    (val) => (val === "" || val === null || val === undefined ? null : String(val).replace(/\D/g, "")),
    z.string().nullable().refine(
      (val) => val === null || val === "" || validarCPF(val),
      { message: "CPF inválido" }
    )
  ),
  nome: z.string().min(1, "Nome é obrigatório"),
  data_exame: z.string().refine(
    (val) => {
      const reg = /^(\d{2})\/(\d{2})\/(\d{4})$/;
      if (!reg.test(val)) return false;
      const [, d, m, a] = val.match(reg)!.map(Number);
      const date = new Date(a, m - 1, d);
      return date.getFullYear() === a && date.getMonth() === m - 1 && date.getDate() === d;
    },
    { message: "Data do exame inválida (formato dd/mm/aaaa esperado)" }
  ),
  idade: z.preprocess(
    (val) => (val === "" || val === null || val === undefined ? 0 : Number(val)),
    z.number().int().min(0, "Idade deve ser um inteiro não negativo")
  ),
  sexo: z.enum(["M", "F"] as const),
  polipo: z.preprocess(
    (val) => (val === "" || val === null || val === undefined ? 0 : Number(val)),
    z.number().int().min(0, "Quantidade de pólipos deve ser maior ou igual a 0")
  ),
  resultado_histopatologico: z.preprocess(
    (val) => (val === "" || val === null || val === undefined ? null : String(val)),
    z.string().nullable().optional()
  ),
  indicacao_exame: z.string().min(1, "Indicação do exame é obrigatória"),
  comorbidades: z.array(z.string()),
  sintomas: z.array(z.string()),
  historico_familiar: z.array(historicoFamiliarSchema),
  endoscopista: z.string().optional().nullable(),
});

export type PacienteFormType = z.infer<typeof pacienteSchema>;
