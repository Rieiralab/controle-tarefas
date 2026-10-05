# Controle de Tarefas

Aplicação web para controlar as tarefas designadas a cada usuário da empresa.
Feita em **Python (Flask) + MySQL**.

## Requisitos atendidos

| Requisito | Onde |
|---|---|
| RF001 – Cadastro de tarefas (nome e tipo diária/semanal/quinzenal/mensal) | *Cadastro de tarefas* (`/tarefas`) |
| RF002 – Cadastro de usuários com nível Supervisor/Operador | *Cadastro de usuários* (`/usuarios`) |
| RF003 – Várias tarefas por usuário | Tela principal: seleção múltipla de tarefas |
| RF004 – Incluir tarefas na mesma tela de consulta | Tela principal: incluir tarefas existentes ou criar uma nova já designada |
| RF005 – Só supervisor cadastra/designa; demais só consultam | Verificado no servidor (`supervisor_required`); o operador não vê os botões e recebe 403 se tentar |
| RNF001 – Consulta exibe código, nome e tipo | Tabela da tela principal |
| RNF002 – Login com usuário e senha | `/login` |

## Banco de dados

Segue o DER do documento (`usuario`, `tarefa`, `usuario_tarefa`), em [schema.sql](schema.sql). Diferenças:

- `usuario.senha` é `VARCHAR(255)` em vez de `CHAR(12)`, para guardar o **hash** da senha, nunca o texto puro.
- `usuario.nome` é único, porque é ele que se usa no login.
- As chaves estrangeiras usam `ON DELETE CASCADE`: excluir um usuário ou uma tarefa remove também os vínculos dela.
- `CHECK` restringe `direito` a `O`/`S` e `tipo` a `D`/`S`/`Q`/`M`.

## Como executar

Pré-requisitos: Python 3.10+ e MySQL 8.

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # preencha DB_USER / DB_PASSWORD / SECRET_KEY

flask init-db               # cria o banco, as tabelas e o supervisor "admin" (pede a senha)
flask run
```

Acesse http://127.0.0.1:5000 e entre com `admin` e a senha informada no `init-db`.

## Regras adicionais

- O sistema exige sempre pelo menos um supervisor: não é possível excluir nem rebaixar o último.
- Um usuário não pode excluir a si mesmo.
- Ao editar um usuário, a senha em branco mantém a atual.
- Todos os formulários têm proteção CSRF.
