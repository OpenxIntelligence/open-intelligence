"""Use the built UI and the same live H1 API as the human browser journey."""
import json


def exercise(cd, value, credentials, tokens, write_grants):
    def click(label):
        cd.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === "
                    + json.dumps(label) + ").click()")

    def submit(selector):
        cd.evaluate("document.querySelector(" + json.dumps(selector) + ").form.requestSubmit()")

    def shown(text):
        cd.wait("document.body.textContent.includes(" + json.dumps(text) + ")", text)

    cd.evaluate("document.querySelector('a[href=\"/veterinary\"]').click()")
    cd.wait("Boolean(document.querySelector('#vet-token'))", "separate veterinary entry")
    value("#vet-token", tokens[0])
    submit("#vet-token")
    click("Register an animal")
    value("#vet-system", "SYNTHETIC-CLINIC")
    value("#vet-ref", "SYNTHETIC-PET")
    cd.evaluate("document.querySelector('input[type=checkbox]').click()")
    submit("#vet-key")
    shown("This credential cannot register animals.")
    previous = credentials[0]["actions"]
    try:
        credentials[0]["actions"] = ["animal_register", "animal_read", "veterinary_case_open", "veterinary_case_read"]
        write_grants()
        submit("#vet-key")
        shown("Registration saved")
        animal = cd.evaluate("document.querySelector('dd').textContent")
        submit("#vet-key")
        shown("Registration recovered")
        click("Check current access and open record")
        shown("This record is unavailable")
        credentials[0]["animal_ids"] = [animal]
        write_grants()
        submit("#vet-animal")
        shown("Animal identity")
        click("Create a case")
        retry_key = cd.evaluate("document.querySelector('#vet-key').value")
        click("Find a record")
        click("Create a case")
        assert cd.evaluate("document.querySelector('#vet-key').value") == retry_key, "Navigation lost the retry identity"
        cd.evaluate("document.querySelector('input[type=checkbox]').click()")
        submit("#vet-key")
        shown("Registration saved")
        click("Check current access and open record")
        cd.wait("document.querySelector('.patient h2')?.textContent === 'Veterinary case'", "scoped veterinary case")
        assert cd.evaluate("Array.from(document.querySelectorAll('dd')).some(e=>e.textContent==='dog')")
        del credentials[0]["animal_ids"]
        write_grants()
        submit("#vet-animal")
        shown("This record is unavailable")
        assert cd.evaluate("!document.querySelector('.patient')")
        cd.command("Page.reload")
        cd.wait("Boolean(document.querySelector('#vet-token'))", "reload clears veterinary credentials")
    finally:
        credentials[0]["actions"] = previous
        credentials[0].pop("animal_ids", None)
        write_grants()
    cd.evaluate("document.querySelector('a[href=\"/\"]').click()")
    cd.wait("document.querySelector('[data-testid=readiness]')?.textContent==='PostgreSQL API ready'",
            "human workspace reopens with independent access")
    print("PASS: veterinary browser registration, scoped animal/case, exact retry, denial, revocation and reload")
