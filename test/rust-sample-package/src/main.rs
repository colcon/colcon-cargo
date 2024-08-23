fn main() {
    println!("Hello, world!");
}

#[cfg(test)]
mod tests {

    #[test]
    fn ok() -> Result<(), ()> {
        Ok(())
    }

    #[test]
    fn err() -> Result<(), ()> {
        Err(())
    }
}
