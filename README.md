# Controle de Tarefas

Sistema web para controlar as tarefas de cada usuário da empresa, feito com Flask e MySQL.

Supervisores cadastram tarefas e usuários e definem quais tarefas cada um tem. Pela própria tela de consulta dá para incluir tarefas já cadastradas ou criar uma nova direto para o usuário. Operadores só consultam.

## Como rodar

Precisa de Python 3.10 ou mais novo e MySQL 8.

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
flask init-db
flask run
```

No `.env`, preencha pelo menos o usuário e a senha do MySQL e uma `SECRET_KEY`. O `flask init-db` cria o banco e as tabelas e pede a senha do primeiro supervisor, que se chama `admin`. Depois é só abrir http://127.0.0.1:5000 e entrar com ele.

## Banco de dados

As tabelas estão em [schema.sql](schema.sql) e seguem o DER do documento, com algumas mudanças:

- a senha é `VARCHAR(255)` em vez de `CHAR(12)`, porque o banco guarda o hash dela e não a senha em si;
- o nome do usuário é único, já que é usado no login;
- excluir um usuário ou uma tarefa apaga também os vínculos entre eles.

## Outras regras

O sistema não deixa ficar sem supervisor: o último não pode ser excluído nem virar operador. Ninguém consegue excluir o próprio usuário. Ao editar um usuário, a senha pode ficar em branco para manter a atual.
